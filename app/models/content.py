"""
Content models - Represents content items and categories.

This handles:
1. Content items (articles, videos, books, etc.)
2. Content categories for organization
3. Content metadata for recommendations
4. Relationships with users and interactions
"""

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, ForeignKey, JSON, Index, Enum as SQLEnum
from typing import List, Optional, Dict, Any
from enum import Enum

from app.database import Base


class ContentType(str, Enum):
    """Enum for different types of content"""
    ARTICLE = "article"
    VIDEO = "video"  
    BOOK = "book"
    PODCAST = "podcast"
    COURSE = "course"


class ContentCategory(Base):
    """
    Content categories for organization and filtering.
    
    Design decisions:
    - Separate table for better normalization
    - Slug for URL-friendly names
    - Description for better UX
    """
    __tablename__ = "content_categories"
    
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    color: Mapped[Optional[str]] = mapped_column(String(7))  # Hex color code
    
    # Relationships
    contents: Mapped[List["Content"]] = relationship(
        "Content",
        back_populates="category"
    )
    
    def __repr__(self) -> str:
        return f"<ContentCategory(id={self.id}, name='{self.name}')>"


class Content(Base):
    """
    Main content model representing all content items.
    
    Design decisions:
    - Single table for all content types (easier queries)
    - Rich metadata in JSON for flexibility
    - Separate category relationship
    - Statistics for trending algorithms
    """
    __tablename__ = "contents"
    
    # Basic information
    title: Mapped[str] = mapped_column(String(500), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    content_type: Mapped[ContentType] = mapped_column(SQLEnum(ContentType), index=True)
    
    # Content data
    body: Mapped[Optional[str]] = mapped_column(Text)  # For articles
    url: Mapped[Optional[str]] = mapped_column(String(1000))  # For external content
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Content metadata for recommendations (flexible JSON structure)
    content_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    # Example: {"tags": ["python", "ai"], "difficulty": "intermediate", "duration": 30}
    
    # Author relationship
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    author: Mapped["User"] = relationship("User", back_populates="contents")
    
    # Category relationship
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("content_categories.id"), index=True)
    category: Mapped[Optional["ContentCategory"]] = relationship(
        "ContentCategory", 
        back_populates="contents"
    )
    
    # Statistics (updated by triggers or background jobs)
    view_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    save_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Recommendation scores (calculated by background jobs)
    trending_score: Mapped[float] = mapped_column(default=0.0, index=True)
    quality_score: Mapped[float] = mapped_column(default=0.0)  # Based on engagement
    
    # Status
    is_published: Mapped[bool] = mapped_column(default=True, index=True)
    is_featured: Mapped[bool] = mapped_column(default=False)
    
    # Relationships
    interactions: Mapped[List["Interaction"]] = relationship(
        "Interaction",
        back_populates="content",
        cascade="all, delete-orphan"
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_content_trending", "trending_score", "created_at"),
        Index("idx_content_category_type", "category_id", "content_type"),
        Index("idx_content_author_published", "author_id", "is_published"),
    )
    
    def __repr__(self) -> str:
        return f"<Content(id={self.id}, title='{self.title[:30]}...')>"
    
    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (likes + saves) / views"""
        if self.view_count == 0:
            return 0.0
        return (self.like_count + self.save_count) / self.view_count
    
    @property
    def tags(self) -> List[str]:
        """Extract tags from metadata"""
        return self.metadata.get("tags", []) if self.metadata else []