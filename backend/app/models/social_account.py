from sqlalchemy.types import Text
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    provider = Column(String(50), nullable=False)
    
    # Increased the length from the default to 255 to ensure
    # the full URN (e.g., "urn:li:person:y3p7QW4Is_") can be stored without truncation.
    provider_user_id = Column(String(255), nullable=False, unique=True)
    
    # Increased length for potentially long access tokens
    access_token = Column(String(1024), nullable=False)

    refresh_token = Column(Text, nullable=True)
    
    expires_at = Column(DateTime, nullable=True)
    
    owner = relationship("User", back_populates="social_accounts")

from .user import User
User.social_accounts = relationship("SocialAccount", back_populates="owner", cascade="all, delete-orphan")