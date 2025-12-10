"""
Interaction models - User interactions with content and other users.

This handles:
1. User-content interactions (likes, saves, views, ratings)
2. User-user interactions (following)
3. Interaction tracking for recommendations
4. Analytics data collection
"""

from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.content import Content

from sqlalchemy import (
    JSON,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InteractionType(str, Enum):
    """Different types of user-content interactions"""

    VIEW = "view"
    LIKE = "like"
    SAVE = "save"
    SHARE = "share"
    RATE = "rate"
    COMMENT = "comment"


class Interaction(Base):
    """
    User interactions with content.

    Design decisions:
    - Single table for all interaction types
    - Optional rating field for rating interactions
    - Metadata for additional context
    - Composite unique constraint to prevent duplicates
    """

    __tablename__ = "interactions"

    # Foreign keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), index=True)

    # Interaction details
    interaction_type: Mapped[InteractionType] = mapped_column(
        SQLEnum(InteractionType), index=True
    )
    rating: Mapped[Optional[float]] = mapped_column(Float)  # 1-5 stars for ratings

    # Additional context (optional)
    interaction_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON
    )  # JSON for flexibility

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="interactions")
    content: Mapped["Content"] = relationship("Content", back_populates="interactions")

    # Constraints and indexes
    __table_args__ = (
        # Prevent duplicate interactions of same type
        UniqueConstraint(
            "user_id",
            "content_id",
            "interaction_type",
            name="unique_user_content_interaction",
        ),
        # Indexes for common queries
        Index("idx_interaction_user_type", "user_id", "interaction_type"),
        Index("idx_interaction_content_type", "content_id", "interaction_type"),
        Index("idx_interaction_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Interaction(id={self.id}, user_id={self.user_id}, type='{self.interaction_type}')>"


class Follow(Base):
    """
    User following relationships.

    Design decisions:
    - Separate table for follows (different from content interactions)
    - Self-referential relationship
    - Unique constraint to prevent duplicate follows
    """

    __tablename__ = "follows"

    # The user who is following
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # The user being followed
    followed_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Relationships
    follower: Mapped["User"] = relationship(
        "User", foreign_keys=[follower_id], back_populates="following"
    )
    followed: Mapped["User"] = relationship(
        "User", foreign_keys=[followed_id], back_populates="followers"
    )

    # Constraints and indexes
    __table_args__ = (
        # Prevent duplicate follows and self-follows
        UniqueConstraint(
            "follower_id", "followed_id", name="unique_follow_relationship"
        ),
        Index("idx_follow_follower", "follower_id"),
        Index("idx_follow_followed", "followed_id"),
    )

    def __repr__(self) -> str:
        return f"<Follow(id={self.id}, follower_id={self.follower_id}, followed_id={self.followed_id})>"
