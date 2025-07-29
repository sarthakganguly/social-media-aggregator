from fastapi import Request
from typing import Optional
from .services import api_client
from .models import User

async def get_current_user_from_cookie(request: Request) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    user_data = await api_client.get_current_user(token)
    if user_data:
        return User(**user_data)
    return None