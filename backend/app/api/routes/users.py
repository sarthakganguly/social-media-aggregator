from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserInDB
from app.dependencies import get_current_user_required # We will reuse this dependency

router = APIRouter()

@router.get("/me", response_model=UserInDB)
async def read_users_me(current_user: User = Depends(get_current_user_required)):
    return current_user