from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False)  # e.g., 'linkedin'
    provider_user_id = Column(String, nullable=False, unique=True)
    access_token = Column(String, nullable=False) # In production, this should be encrypted
    # refresh_token = Column(String, nullable=True) # For long-term access
    expires_at = Column(DateTime, nullable=True)
    
    owner = relationship("User", back_populates="social_accounts")

# Add the relationship to the User model
from .user import User
User.social_accounts = relationship("SocialAccount", back_populates="owner", cascade="all, delete-orphan")