from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from app.models.post import PostStatus

class PostBase(BaseModel):
    content: str

class PostCreate(PostBase):
    channels: Optional[List[str]] = []

class PostInDB(PostBase):
    id: int
    user_id: int
    status: PostStatus
    created_at: datetime
    
    class Config:
        from_attributes = True