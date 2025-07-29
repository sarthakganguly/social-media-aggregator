from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import httpx
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.db.session import get_db
from app.models.user import User
from app.models.social_account import SocialAccount
from app.dependencies import get_current_user_required
from app.core.config import settings

router = APIRouter()

class LinkedInConnectRequest(BaseModel):
    code: str

class DisconnectRequest(BaseModel):
    provider: str

@router.post("/connect")
async def connect_linkedin_account(
    request: LinkedInConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    token_params = {
        "grant_type": "authorization_code",
        "code": request.code,
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=token_params)
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Could not get access token from LinkedIn: {token_response.text}")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")
        
        # --- THE CORRECT ENDPOINT FOR OPENID SCOPES ---
        profile_url = "https://api.linkedin.com/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await client.get(profile_url, headers=headers)
        
        if profile_response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Could not fetch user profile from LinkedIn: {profile_response.text}")
            
        profile_data = profile_response.json()

        # --- CONSTRUCT THE URN FROM THE 'sub' FIELD ---
        sub_id = profile_data.get("sub")
        if not sub_id:
            raise HTTPException(status_code=500, detail="LinkedIn profile 'sub' ID not found in API response.")
        
        # This is the correct format required by the ugcPosts API
        linkedin_user_urn = f"urn:li:person:{sub_id}"

    existing_account = db.query(SocialAccount).filter_by(provider="linkedin", provider_user_id=linkedin_user_urn).first()
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None

    if existing_account:
        if existing_account.user_id != current_user.id:
             raise HTTPException(status_code=400, detail="This LinkedIn account is already linked to another user.")
        existing_account.access_token = access_token
        existing_account.expires_at = expires_at
    else:
        new_account = SocialAccount(user_id=current_user.id, provider="linkedin", provider_user_id=linkedin_user_urn, access_token=access_token, expires_at=expires_at)
        db.add(new_account)
    
    db.commit()
    return {"status": "success", "provider": "linkedin"}

@router.post("/disconnect")
async def disconnect_account(request: DisconnectRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    account_to_delete = db.query(SocialAccount).filter_by(user_id=current_user.id, provider=request.provider).first()
    if not account_to_delete:
        raise HTTPException(status_code=404, detail=f"{request.provider.capitalize()} account not found.")
    db.delete(account_to_delete)
    db.commit()
    return {"status": "success", "detail": f"{request.provider.capitalize()} account has been disconnected."}

@router.get("/accounts")
async def get_connected_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    accounts = db.query(SocialAccount).filter_by(user_id=current_user.id).all()
    return [{"provider": acc.provider} for acc in accounts]