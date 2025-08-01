from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import httpx
from pydantic import BaseModel
from datetime import datetime, timedelta
import os

from app.db.session import get_db
from app.models.user import User
from app.models.social_account import SocialAccount
from app.dependencies import get_current_user_required
from app.core.config import settings

router = APIRouter()

class XConnectRequest(BaseModel):
    code: str
    code_verifier: str

@router.post("/connect", status_code=status.HTTP_201_CREATED)
async def connect_twitter_account(
    request: XConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Handles the final step of the OAuth 2.0 PKCE flow for X (Twitter).
    Exchanges an authorization code for an access token and refresh token.
    """
    token_url = "https://api.twitter.com/2/oauth2/token"
    # The redirect URI must exactly match one of the URIs configured in the X Dev Portal
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI").replace("linkedin", "twitter")

    async with httpx.AsyncClient() as client:
        # 1. Exchange the authorization code and verifier for tokens
        token_response = await client.post(
            token_url,
            data={
                "code": request.code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": request.code_verifier,
                "client_id": settings.X_CLIENT_ID, # Client ID is passed in the body for X
            },
            # Client Secret is sent as Basic Auth
            auth=(settings.X_CLIENT_ID, settings.X_CLIENT_SECRET),
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Could not get access token from X: {token_response.text}")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in") # Typically 7200 seconds (2 hours)

        # 2. Use the new access token to get the user's profile info
        profile_url = "https://api.twitter.com/2/users/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await client.get(profile_url, headers=headers)

        if profile_response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Could not fetch user profile from X: {profile_response.text}")

        profile_data = profile_response.json().get("data", {})
        twitter_user_id = profile_data.get("id")

    # 3. Save or update the social account in the database
    existing_account = db.query(SocialAccount).filter_by(
        provider="twitter", provider_user_id=twitter_user_id
    ).first()
    
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None

    if existing_account:
        if existing_account.user_id != current_user.id:
            raise HTTPException(status_code=400, detail="This X account is already linked to another user.")
        
        existing_account.access_token = access_token
        existing_account.refresh_token = refresh_token
        existing_account.expires_at = expires_at
    else:
        new_account = SocialAccount(
            user_id=current_user.id,
            provider="twitter",
            provider_user_id=twitter_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        db.add(new_account)

    db.commit()
    
    return {"status": "success", "provider": "twitter", "username": profile_data.get("username")}