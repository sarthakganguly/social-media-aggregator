from pydantic import BaseModel, EmailStr
from datetime import datetime

# The User model is already correct
class User(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool

# New Post model for the frontend
class Post(BaseModel):
    id: int
    content: str
    status: str
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True