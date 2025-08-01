from fastapi import FastAPI, Request, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime
from typing import Optional, List
import os
import secrets
import hashlib  
import base64   

from .dependencies import get_current_user_from_cookie
from .services import api_client
from .models import User, Post

app = FastAPI(title="Social Media Aggregator - Frontend")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates", context_processors=[lambda request: {"now": datetime.utcnow}])

async def user_to_context(request: Request, current_user: Optional[User] = Depends(get_current_user_from_cookie)):
    return {"current_user": current_user}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, context: dict = Depends(user_to_context)):
    if context.get("current_user"): return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", {"request": request, **context})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, context: dict = Depends(user_to_context)):
    if context.get("current_user"): return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", {"request": request, "msg": request.query_params.get('msg'), "error": request.query_params.get('error'), **context})

@app.post("/login")
async def handle_login(username: str = Form(...), password: str = Form(...)):
    token_data = await api_client.login_for_token(username, password)
    if not token_data: return RedirectResponse(url="/login?error=Invalid credentials", status_code=303)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {token_data['access_token']}", httponly=True)
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, context: dict = Depends(user_to_context)):
    return templates.TemplateResponse("register.html", {"request": request, **context})

@app.post("/register")
async def handle_registration(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...), context: dict = Depends(user_to_context)):
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Passwords do not match", **context})
    success, detail = await api_client.register_user(username, email, password)
    if not success:
        return templates.TemplateResponse("register.html", {"request": request, "error": detail, **context})
    return RedirectResponse(url="/login?msg=Registration successful!", status_code=303)

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

@app.get("/auth/linkedin/start")
async def start_linkedin_oauth():
    state = secrets.token_hex(16)
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
    scope = os.getenv("LINKEDIN_SCOPE")
    linkedin_auth_url = (f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}&scope={scope}")
    response = RedirectResponse(url=linkedin_auth_url)
    response.set_cookie(key="linkedin_oauth_state", value=state, httponly=True)
    return response

@app.get("/auth/linkedin/callback")
async def handle_linkedin_callback(request: Request):
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")
    if error:
        return RedirectResponse(url=f"/dashboard?error={error_description or error}", status_code=303)
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    stored_state = request.cookies.get("linkedin_oauth_state")
    if not state or state != stored_state:
        return RedirectResponse(url="/dashboard?error=Invalid state. CSRF attack suspected.", status_code=303)
    if not code:
        return RedirectResponse(url="/dashboard?error=Authorization code not received from LinkedIn.", status_code=303)
    token = request.cookies.get("access_token")
    success, detail = await api_client.connect_linkedin_account(token, code)
    if success:
        return RedirectResponse(url=f"/dashboard?msg=Successfully connected LinkedIn account.", status_code=303)
    else:
        return RedirectResponse(url=f"/dashboard?error={detail}", status_code=303)

@app.post("/auth/disconnect")
async def handle_disconnect(request: Request, provider: str = Form(...)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login?error=Authentication session has expired.", status_code=303)
    success, detail = await api_client.disconnect_social_account(token, provider)
    if success:
        return RedirectResponse(url=f"/dashboard?msg={detail}", status_code=303)
    else:
        return RedirectResponse(url=f"/dashboard?error={detail}", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, context: dict = Depends(user_to_context)):
    current_user = context.get("current_user")
    if not current_user:
        return RedirectResponse(url="/login?error=Please log in", status_code=307)
    
    token = request.cookies.get("access_token")
    connected_accounts_data = await api_client.get_connected_accounts(token)
    connected_providers = [acc['provider'] for acc in connected_accounts_data]
    channels = [
        {'name': 'X (Twitter)', 'icon_path': 'icons/x.png', 'provider': 'twitter', 'connected': 'twitter' in connected_providers},
        {'name': 'LinkedIn', 'icon_path': 'icons/linkedin.png', 'provider': 'linkedin', 'connected': 'linkedin' in connected_providers},
        {'name': 'Instagram', 'icon_path': 'icons/instagram.png', 'provider': 'instagram', 'connected': 'instagram' in connected_providers},
        {'name': 'Facebook', 'icon_path': 'icons/facebook.png', 'provider': 'facebook', 'connected': 'facebook' in connected_providers}
    ]
    
    context["channels"] = channels
    context["msg"] = request.query_params.get("msg")
    context["error"] = request.query_params.get("error")
    return templates.TemplateResponse("dashboard.html", {"request": request, **context})

@app.post("/dashboard/posts/create")
async def handle_post_creation(request: Request, content: str = Form(...), channels: Optional[List[str]] = Form(None), action: str = Form(...)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login?error=Authentication session has expired.", status_code=303)
    if action == 'post_now' and not channels:
        return RedirectResponse(url=f"/dashboard?error=Please select at least one channel to post to.", status_code=303)
    success, detail = await api_client.create_post(token, content, channels or [], action)
    if success:
        return RedirectResponse(url=f"/dashboard?msg={detail}", status_code=303)
    else:
        return RedirectResponse(url=f"/dashboard?error={detail}", status_code=303)

@app.get("/drafts", response_class=HTMLResponse)
async def drafts_page(request: Request, context: dict = Depends(user_to_context)):
    current_user = context.get("current_user")
    if not current_user:
        return RedirectResponse(url="/login?error=Please log in", status_code=307)
    
    token = request.cookies.get("access_token")
    drafts_data = await api_client.get_drafts(token)
    drafts = [Post(**draft) for draft in drafts_data]
    
    context["drafts"] = drafts
    context["msg"] = request.query_params.get("msg")
    context["error"] = request.query_params.get("error")
    return templates.TemplateResponse("drafts.html", {"request": request, **context})

@app.post("/drafts/{post_id}/delete")
async def handle_delete_draft(request: Request, post_id: int):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login?error=Authentication session has expired.", status_code=303)
    
    success, detail = await api_client.delete_post(token, post_id)
    
    if success:
        return RedirectResponse(url=f"/drafts?msg={detail}", status_code=303)
    else:
        return RedirectResponse(url=f"/drafts?error={detail}", status_code=303)

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, context: dict = Depends(user_to_context)):
    if not context.get("current_user"): return RedirectResponse(url="/login?error=Please log in", status_code=307)
    return templates.TemplateResponse("history.html", {"request": request, **context})

@app.get("/auth/twitter/start")
async def start_twitter_oauth():
    state = secrets.token_hex(16)
    # PKCE Code Verifier and Challenge
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).rstrip(b'=').decode('utf-8')

    client_id = os.getenv("X_CLIENT_ID")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI").replace("linkedin", "twitter") # Reuse and replace
    scopes = os.getenv("X_SCOPES")

    twitter_auth_url = (
        f"https://twitter.com/i/oauth2/authorize?response_type=code"
        f"&client_id={client_id}&redirect_uri={redirect_uri}&scope={scopes}"
        f"&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"
    )

    response = RedirectResponse(url=twitter_auth_url)
    response.set_cookie(key="twitter_oauth_state", value=state, httponly=True)
    response.set_cookie(key="twitter_code_verifier", value=code_verifier, httponly=True)
    return response

@app.get("/auth/twitter/callback")
async def handle_twitter_callback(request: Request):
    error = request.query_params.get("error")
    if error:
        return RedirectResponse(url=f"/dashboard?error={error}", status_code=303)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    stored_state = request.cookies.get("twitter_oauth_state")
    code_verifier = request.cookies.get("twitter_code_verifier")
    
    if not state or state != stored_state:
        return RedirectResponse(url="/dashboard?error=Invalid state.", status_code=303)

    token = request.cookies.get("access_token")
    success, detail = await api_client.connect_twitter_account(token, code, code_verifier)

    if success:
        return RedirectResponse(url=f"/dashboard?msg={detail}", status_code=303)
    else:
        return RedirectResponse(url=f"/dashboard?error={detail}", status_code=303)