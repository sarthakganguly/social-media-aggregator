from pydantic import BaseModel
from datetime import datetime

class SocialAccountBase(BaseModel):
    provider: str
    provider_user_id: str

class SocialAccountCreate(SocialAccountBase):
    access_token: str
    expires_at: datetime | None = None

class SocialAccountInDB(SocialAccountBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True