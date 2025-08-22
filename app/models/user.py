"""
User model - Represents users in the system.

This model handles:
1. User authentication data (email, password)
2. User profile information
3. User preferences for recommendations
4. Relationships with other entities
"""

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Boolean, JSON
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import Base


class User(Base):
    """
    User model representing system users.
    
    Design decisions:
    - Email as unique identifier (better UX than username)
    - JSON field for preferences (flexible, no schema changes needed)
    - Separate is_active flag for soft deletes
    - Profile fields for recommendation personalization
    """
    __tablename__ = "users"
    
    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Recommendation preferences
    preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    # Example: {"categories": ["tech", "science"], "max_recommendations": 50}
    
    # Statistics (for recommendation algorithms)
    total_interactions: Mapped[int] = mapped_column(default=0)
    last_active: Mapped[Optional[datetime]] = mapped_column()
    
    # Relationships (defined as strings to avoid circular imports)
    contents: Mapped[List["Content"]] = relationship(
        "Content", 
        back_populates="author",
        cascade="all, delete-orphan"
    )
    
    interactions: Mapped[List["Interaction"]] = relationship(
        "Interaction",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Following relationships
    following: Mapped[List["Follow"]] = relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan"
    )
    
    followers: Mapped[List["Follow"]] = relationship(
        "Follow",
        foreign_keys="Follow.followed_id", 
        back_populates="followed",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
    
    @property
    def follower_count(self) -> int:
        """Number of followers"""
        return len(self.followers)
    
    @property  
    def following_count(self) -> int:
        """Number of users this user follows"""
        return len(self.following)