"""
Content schemas for request/response validation.

This provides:
1. Content creation and update schemas
2. Content response formatting
3. Category management schemas
4. Search and filtering schemas
5. Content interaction schemas
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, validator

from app.models.content import ContentType


class ContentTypeEnum(str, Enum):
    """Content type enumeration for API validation."""

    ARTICLE = "article"
    VIDEO = "video"
    BOOK = "book"
    PODCAST = "podcast"
    COURSE = "course"


class DifficultyLevel(str, Enum):
    """Content difficulty levels."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


# Request Schemas


class ContentCreateRequest(BaseModel):
    """Schema for content creation requests."""

    title: str = Field(..., min_length=3, max_length=500, description="Content title")
    description: Optional[str] = Field(
        None, max_length=2000, description="Content description"
    )
    content_type: ContentTypeEnum = Field(..., description="Type of content")
    body: Optional[str] = Field(
        None, description="Content body (for articles, courses)"
    )
    url: Optional[HttpUrl] = Field(
        None, description="External URL (for videos, podcasts)"
    )
    category_id: Optional[int] = Field(None, description="Content category ID")
    tags: Optional[List[str]] = Field(
        default=[], description="Content tags for searchability"
    )
    difficulty: Optional[DifficultyLevel] = Field(
        None, description="Content difficulty level"
    )
    duration_minutes: Optional[int] = Field(
        None, ge=1, le=1440, description="Content duration in minutes"  # Max 24 hours
    )
    is_featured: Optional[bool] = Field(
        default=False, description="Whether content should be featured"
    )

    @validator("tags")
    def validate_tags(cls, v):
        """Validate tags list"""
        if v is None:
            return []

        # Limit number of tags
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")

        # Clean and validate individual tags
        clean_tags = []
        for tag in v:
            if isinstance(tag, str):
                clean_tag = tag.strip().lower()
                if len(clean_tag) > 0 and len(clean_tag) <= 50:
                    clean_tags.append(clean_tag)

        return clean_tags

    @validator("body")
    def validate_body_for_content_type(cls, v, values):
        """Validate body content based on content type"""
        content_type = values.get("content_type")

        if content_type in [ContentTypeEnum.ARTICLE, ContentTypeEnum.COURSE]:
            if not v or len(v.strip()) < 100:
                raise ValueError(
                    f"{content_type} must have substantial body content (min 100 characters)"
                )

        return v

    @validator("url")
    def validate_url_for_content_type(cls, v, values):
        """Validate URL based on content type"""
        content_type = values.get("content_type")

        if content_type in [ContentTypeEnum.VIDEO, ContentTypeEnum.PODCAST]:
            if not v:
                raise ValueError(f"{content_type} must have a URL")

        return v

    class Config:
        schema_extra = {
            "example": {
                "title": "Introduction to Machine Learning",
                "description": "A comprehensive guide to machine learning fundamentals",
                "content_type": "article",
                "body": "Machine learning is a subset of artificial intelligence...",
                "category_id": 1,
                "tags": ["machine-learning", "ai", "python"],
                "difficulty": "intermediate",
                "duration_minutes": 30,
            }
        }


class ContentUpdateRequest(BaseModel):
    """Schema for content update requests."""

    title: Optional[str] = Field(
        None, min_length=3, max_length=500, description="Updated content title"
    )
    description: Optional[str] = Field(
        None, max_length=2000, description="Updated content description"
    )
    body: Optional[str] = Field(None, description="Updated content body")
    url: Optional[HttpUrl] = Field(None, description="Updated external URL")
    category_id: Optional[int] = Field(None, description="Updated category ID")
    tags: Optional[List[str]] = Field(None, description="Updated content tags")
    difficulty: Optional[DifficultyLevel] = Field(
        None, description="Updated difficulty level"
    )
    duration_minutes: Optional[int] = Field(
        None, ge=1, le=1440, description="Updated duration in minutes"
    )
    is_published: Optional[bool] = Field(
        None, description="Whether content is published"
    )
    is_featured: Optional[bool] = Field(None, description="Whether content is featured")

    @validator("tags")
    def validate_tags(cls, v):
        """Validate tags list"""
        if v is None:
            return None

        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")

        return [tag.strip().lower() for tag in v if tag.strip()]

    class Config:
        schema_extra = {
            "example": {
                "title": "Advanced Machine Learning Techniques",
                "description": "Updated description with more details",
                "tags": ["machine-learning", "advanced", "neural-networks"],
                "difficulty": "advanced",
            }
        }


# Response Schemas


class AuthorResponse(BaseModel):
    """Schema for content author information."""

    id: int = Field(..., description="Author's user ID")
    full_name: Optional[str] = Field(None, description="Author's full name")
    email: str = Field(..., description="Author's email")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "full_name": "John Doe",
                "email": "john.doe@example.com",
            }
        }


class CategoryResponse(BaseModel):
    """Schema for content category information."""

    id: int = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    slug: str = Field(..., description="Category URL slug")
    description: Optional[str] = Field(None, description="Category description")
    color: Optional[str] = Field(None, description="Category color code")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Technology",
                "slug": "technology",
                "description": "Tech-related content",
                "color": "#007bff",
            }
        }


class ContentStatsResponse(BaseModel):
    """Schema for content statistics."""

    views: int = Field(default=0, description="View count")
    likes: int = Field(default=0, description="Like count")
    saves: int = Field(default=0, description="Save count")
    shares: int = Field(default=0, description="Share count")
    engagement_rate: float = Field(default=0.0, description="Engagement rate")

    class Config:
        schema_extra = {
            "example": {
                "views": 1500,
                "likes": 120,
                "saves": 45,
                "shares": 23,
                "engagement_rate": 0.125,
            }
        }


class ContentResponse(BaseModel):
    """Schema for content responses."""

    id: int = Field(..., description="Content ID")
    title: str = Field(..., description="Content title")
    description: Optional[str] = Field(None, description="Content description")
    content_type: str = Field(..., description="Content type")
    body: Optional[str] = Field(None, description="Content body")
    url: Optional[str] = Field(None, description="External URL")
    image_url: Optional[str] = Field(None, description="Content image URL")

    # Metadata
    tags: List[str] = Field(default=[], description="Content tags")
    difficulty: Optional[str] = Field(None, description="Difficulty level")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes")

    # Status
    is_published: bool = Field(..., description="Publication status")
    is_featured: bool = Field(default=False, description="Featured status")

    # Relationships
    author: Optional[AuthorResponse] = Field(None, description="Content author")
    category: Optional[CategoryResponse] = Field(None, description="Content category")

    # Statistics
    stats: ContentStatsResponse = Field(..., description="Content statistics")

    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "title": "Introduction to Machine Learning",
                "description": "A comprehensive guide to ML fundamentals",
                "content_type": "article",
                "body": "Machine learning is a subset of AI...",
                "tags": ["machine-learning", "ai", "python"],
                "difficulty": "intermediate",
                "duration_minutes": 30,
                "is_published": True,
                "is_featured": False,
                "author": {
                    "id": 1,
                    "full_name": "John Doe",
                    "email": "john@example.com",
                },
                "category": {"id": 1, "name": "Technology", "slug": "technology"},
                "stats": {
                    "views": 1500,
                    "likes": 120,
                    "saves": 45,
                    "shares": 23,
                    "engagement_rate": 0.125,
                },
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-16T14:20:00Z",
            }
        }


class ContentSummaryResponse(BaseModel):
    """Schema for content summary (used in lists)."""

    id: int = Field(..., description="Content ID")
    title: str = Field(..., description="Content title")
    description: Optional[str] = Field(None, description="Content description")
    content_type: str = Field(..., description="Content type")
    image_url: Optional[str] = Field(None, description="Content image URL")

    # Key metadata
    tags: List[str] = Field(default=[], description="Content tags")
    difficulty: Optional[str] = Field(None, description="Difficulty level")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes")

    # Author info
    author_name: Optional[str] = Field(None, description="Author name")

    # Category info
    category_name: Optional[str] = Field(None, description="Category name")

    # Key stats
    view_count: int = Field(default=0, description="View count")
    like_count: int = Field(default=0, description="Like count")

    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "title": "Introduction to Machine Learning",
                "description": "A comprehensive guide to ML fundamentals",
                "content_type": "article",
                "tags": ["machine-learning", "ai"],
                "difficulty": "intermediate",
                "duration_minutes": 30,
                "author_name": "John Doe",
                "category_name": "Technology",
                "view_count": 1500,
                "like_count": 120,
                "created_at": "2024-01-15T10:30:00Z",
            }
        }


class ContentListResponse(BaseModel):
    """Schema for paginated content lists."""

    items: List[ContentSummaryResponse] = Field(..., description="Content items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")

    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "id": 1,
                        "title": "Introduction to Machine Learning",
                        "content_type": "article",
                        "author_name": "John Doe",
                        "view_count": 1500,
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                ],
                "total": 150,
                "page": 1,
                "pages": 8,
                "has_next": True,
                "has_prev": False,
            }
        }


# Category Schemas


class CategoryCreateRequest(BaseModel):
    """Schema for category creation."""

    name: str = Field(..., min_length=2, max_length=100, description="Category name")
    description: Optional[str] = Field(
        None, max_length=500, description="Category description"
    )
    color: Optional[str] = Field(
        None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Category color (hex format)"
    )

    @validator("name")
    def validate_name(cls, v):
        """Validate category name"""
        if not v.strip():
            raise ValueError("Category name cannot be empty")
        return v.strip().title()

    class Config:
        schema_extra = {
            "example": {
                "name": "Technology",
                "description": "Technology-related content",
                "color": "#007bff",
            }
        }


# Search and Filter Schemas


class ContentSearchRequest(BaseModel):
    """Schema for content search requests."""

    query: str = Field(..., min_length=2, max_length=200, description="Search query")
    content_type: Optional[ContentTypeEnum] = Field(
        None, description="Filter by content type"
    )
    category_id: Optional[int] = Field(None, description="Filter by category")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    difficulty: Optional[DifficultyLevel] = Field(
        None, description="Filter by difficulty"
    )
    author_id: Optional[int] = Field(None, description="Filter by author")

    class Config:
        schema_extra = {
            "example": {
                "query": "machine learning",
                "content_type": "article",
                "category_id": 1,
                "tags": ["python", "ai"],
                "difficulty": "intermediate",
            }
        }


# Interaction Schemas


class ContentInteractionRequest(BaseModel):
    """Schema for content interaction requests."""

    interaction_type: str = Field(
        ..., description="Type of interaction (like, save, share)"
    )
    rating: Optional[float] = Field(
        None, ge=1.0, le=5.0, description="Rating (1-5 stars)"
    )

    @validator("interaction_type")
    def validate_interaction_type(cls, v):
        """Validate interaction type"""
        valid_types = ["like", "save", "share", "rate"]
        if v.lower() not in valid_types:
            raise ValueError(
                f'Interaction type must be one of: {", ".join(valid_types)}'
            )
        return v.lower()

    class Config:
        schema_extra = {"example": {"interaction_type": "like"}}
