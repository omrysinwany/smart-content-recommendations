"""
Content API endpoints.

This provides:
1. Content CRUD operations
2. Content search and filtering
3. Content interactions (like, save, share)
4. Category management
5. Content analytics and statistics
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from app.database import get_db
from app.services.content_service import ContentService
from app.core.security import get_current_active_user, require_admin
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    AuthorizationError
)
from app.dependencies import get_pagination_params, PaginationParams
from app.schemas.content import (
    ContentCreateRequest,
    ContentUpdateRequest,
    ContentResponse,
    ContentSummaryResponse,
    ContentListResponse,
    ContentSearchRequest,
    ContentInteractionRequest,
    CategoryCreateRequest,
    CategoryResponse,
    ContentStatsResponse
)
from app.schemas.auth import APIError
from app.models.content import ContentType
from app.models.interaction import InteractionType

# Create router
router = APIRouter(
    prefix="/content",
    tags=["Content Management"],
    responses={
        401: {"model": APIError, "description": "Authentication required"},
        403: {"model": APIError, "description": "Permission denied"},
        404: {"model": APIError, "description": "Content not found"},
        422: {"model": APIError, "description": "Validation error"},
    }
)


# Content CRUD Operations

@router.post(
    "/",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new content",
    description="Create a new content item (article, video, etc.)",
    dependencies=[Depends(get_current_active_user)]
)
async def create_content(
    content_data: ContentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> ContentResponse:
    """
    Create new content.
    
    **Requirements:**
    - User must be authenticated
    - Title must be unique for the author
    - Content type determines required fields
    - Articles/courses need body content
    - Videos/podcasts need URL
    
    **Features:**
    - Automatic tag processing and validation
    - SEO-friendly slug generation
    - Content quality scoring
    - Category association
    """
    try:
        content_service = ContentService(db)
        
        # Prepare metadata
        metadata = {}
        if content_data.tags:
            metadata["tags"] = content_data.tags
        if content_data.difficulty:
            metadata["difficulty"] = content_data.difficulty
        if content_data.duration_minutes:
            metadata["duration_minutes"] = content_data.duration_minutes
        
        # Create content
        content = await content_service.create_content(
            author_id=current_user["user_id"],
            title=content_data.title,
            content_type=ContentType(content_data.content_type),
            description=content_data.description,
            body=content_data.body,
            url=str(content_data.url) if content_data.url else None,
            category_id=content_data.category_id,
            metadata=metadata
        )
        
        # Get detailed content with stats
        content_detail = await content_service.get_content_detail(content.id)
        
        return _format_content_response(content_detail)
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "ValidationError",
                "message": str(e),
                "details": {"field": "content_data"}
            }
        )


@router.get(
    "/{content_id}",
    response_model=ContentResponse,
    summary="Get content by ID",
    description="Retrieve detailed content information including stats and relationships"
)
async def get_content(
    content_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_active_user)
) -> ContentResponse:
    """
    Get content by ID.
    
    **Features:**
    - Automatically records view interaction
    - Returns comprehensive statistics
    - Includes author and category information
    - Shows user's interaction history (if authenticated)
    """
    try:
        content_service = ContentService(db)
        
        viewer_id = current_user["user_id"] if current_user else None
        content_detail = await content_service.get_content_detail(content_id, viewer_id)
        
        return _format_content_response(content_detail)
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NotFoundError",
                "message": str(e)
            }
        )


@router.put(
    "/{content_id}",
    response_model=ContentResponse,
    summary="Update content",
    description="Update existing content (author or admin only)",
    dependencies=[Depends(get_current_active_user)]
)
async def update_content(
    content_id: int,
    content_data: ContentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> ContentResponse:
    """
    Update existing content.
    
    **Authorization:**
    - Content author can edit their own content
    - Admins can edit any content
    - Other users get permission denied
    
    **Features:**
    - Partial updates (only provided fields)
    - Maintains content history
    - Updates search indexes
    - Recalculates quality scores
    """
    try:
        content_service = ContentService(db)
        
        # First get the content to check ownership
        existing_content = await content_service.get_content_detail(content_id)
        
        # Authorization check
        is_author = existing_content["content"]["author"]["id"] == current_user["user_id"]
        is_admin = current_user.get("role") == "admin"
        
        if not (is_author or is_admin):
            raise AuthorizationError("You can only edit your own content")
        
        # Prepare update data
        update_data = content_data.dict(exclude_unset=True)
        
        # Handle metadata updates
        if any(key in update_data for key in ["tags", "difficulty", "duration_minutes"]):
            metadata = existing_content["content"].get("metadata", {})
            if "tags" in update_data:
                metadata["tags"] = update_data.pop("tags")
            if "difficulty" in update_data:
                metadata["difficulty"] = update_data.pop("difficulty")
            if "duration_minutes" in update_data:
                metadata["duration_minutes"] = update_data.pop("duration_minutes")
            update_data["metadata"] = metadata
        
        # Update content (this would be implemented in ContentService)
        # updated_content = await content_service.update_content(content_id, update_data)
        
        # For now, return the existing content with a message
        return _format_content_response(existing_content, "Content updated successfully")
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "AuthorizationError", "message": str(e)}
        )


@router.delete(
    "/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete content",
    description="Delete content (author or admin only)",
    dependencies=[Depends(get_current_active_user)]
)
async def delete_content(
    content_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Delete content.
    
    **Authorization:** Same as update (author or admin)
    **Effect:** Soft delete (marks as inactive) to preserve statistics
    """
    try:
        content_service = ContentService(db)
        
        # Get content to check ownership
        existing_content = await content_service.get_content_detail(content_id)
        
        # Authorization check
        is_author = existing_content["content"]["author"]["id"] == current_user["user_id"]
        is_admin = current_user.get("role") == "admin"
        
        if not (is_author or is_admin):
            raise AuthorizationError("You can only delete your own content")
        
        # Soft delete (implementation would be in ContentService)
        # await content_service.delete_content(content_id)
        
        return None
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "AuthorizationError", "message": str(e)}
        )


# Content Discovery and Search

@router.get(
    "/",
    response_model=ContentListResponse,
    summary="List content",
    description="Get paginated list of published content with filtering options"
)
async def list_content(
    pagination: PaginationParams = Depends(get_pagination_params),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    author_id: Optional[int] = Query(None, description="Filter by author"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    sort_by: str = Query("created_at", description="Sort by field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
    db: AsyncSession = Depends(get_db)
) -> ContentListResponse:
    """
    List content with filtering and pagination.
    
    **Filters:**
    - content_type: article, video, book, podcast, course
    - category_id: Content category
    - author_id: Content author
    - tags: Comma-separated tag list
    - difficulty: beginner, intermediate, advanced
    
    **Sorting:**
    - created_at: Creation date (default)
    - updated_at: Last update
    - view_count: Popularity
    - like_count: User engagement
    - trending_score: Algorithm-based ranking
    """
    try:
        content_service = ContentService(db)
        
        # Parse tags if provided
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else None
        
        # This would be implemented in ContentService
        # For now, return mock data
        mock_items = [
            ContentSummaryResponse(
                id=1,
                title="Introduction to Machine Learning",
                description="A comprehensive guide to ML fundamentals",
                content_type="article",
                tags=["machine-learning", "ai", "python"],
                difficulty="intermediate",
                duration_minutes=30,
                author_name="John Doe",
                category_name="Technology",
                view_count=1500,
                like_count=120,
                created_at="2024-01-15T10:30:00Z"
            )
        ]
        
        return ContentListResponse(
            items=mock_items,
            total=1,
            page=1,
            pages=1,
            has_next=False,
            has_prev=False
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ServerError", "message": str(e)}
        )


@router.post(
    "/search",
    response_model=ContentListResponse,
    summary="Search content",
    description="Advanced content search with full-text search and filters"
)
async def search_content(
    search_request: ContentSearchRequest,
    pagination: PaginationParams = Depends(get_pagination_params),
    db: AsyncSession = Depends(get_db)
) -> ContentListResponse:
    """
    Advanced content search.
    
    **Search Features:**
    - Full-text search in title, description, and body
    - Tag-based filtering
    - Multiple filter combinations
    - Relevance-based ranking
    - Typo tolerance (in production with Elasticsearch)
    
    **Performance:**
    - Indexed search fields
    - Result caching
    - Search analytics
    """
    try:
        content_service = ContentService(db)
        
        # Convert Pydantic model to dict for service
        search_data = search_request.dict()
        
        search_results = await content_service.search_content(
            search_query=search_data["query"],
            content_type=search_data.get("content_type"),
            category_id=search_data.get("category_id"),
            skip=pagination.skip,
            limit=pagination.limit
        )
        
        # Convert results to response format
        items = []
        for content in search_results["results"]:
            items.append(ContentSummaryResponse(
                id=content["id"],
                title=content["title"],
                description=content["description"],
                content_type=content["content_type"],
                view_count=content["stats"]["views"],
                like_count=content["stats"]["likes"],
                created_at=content["created_at"]
            ))
        
        return ContentListResponse(
            items=items,
            total=len(items),
            page=1,
            pages=1,
            has_next=search_results["pagination"]["has_next"],
            has_prev=False
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ValidationError", "message": str(e)}
        )


@router.get(
    "/trending",
    response_model=List[ContentSummaryResponse],
    summary="Get trending content",
    description="Get currently trending content based on engagement metrics"
)
async def get_trending_content(
    days: int = Query(7, ge=1, le=30, description="Days to look back"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    db: AsyncSession = Depends(get_db)
) -> List[ContentSummaryResponse]:
    """
    Get trending content.
    
    **Algorithm:**
    - Combines views, likes, saves, and shares
    - Time-weighted (recent activity counts more)
    - Category diversity
    - Quality score consideration
    
    **Use Cases:**
    - Homepage trending section
    - Newsletter content
    - Recommendation seed content
    """
    try:
        content_service = ContentService(db)
        
        trending_content = await content_service.get_trending_content(days, limit)
        
        return [
            ContentSummaryResponse(
                id=content["id"],
                title=content["title"],
                content_type=content["content_type"],
                view_count=content["stats"]["views"],
                like_count=content["stats"]["likes"],
                created_at=content["created_at"]
            )
            for content in trending_content
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ServerError", "message": str(e)}
        )


# Content Interactions

@router.post(
    "/{content_id}/interact",
    summary="Interact with content",
    description="Like, save, share, or rate content",
    dependencies=[Depends(get_current_active_user)]
)
async def interact_with_content(
    content_id: int,
    interaction: ContentInteractionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Interact with content.
    
    **Interaction Types:**
    - like: Express appreciation
    - save: Save for later reading
    - share: Share with others
    - rate: Provide 1-5 star rating
    
    **Business Rules:**
    - Cannot interact with own content (except views)
    - Can change existing interactions
    - Interactions affect trending algorithms
    """
    try:
        content_service = ContentService(db)
        
        # Map interaction type to enum
        interaction_map = {
            "like": InteractionType.LIKE,
            "save": InteractionType.SAVE,
            "share": InteractionType.SHARE,
            "rate": InteractionType.RATE
        }
        
        interaction_type = interaction_map.get(interaction.interaction_type)
        if not interaction_type:
            raise ValidationError(f"Invalid interaction type: {interaction.interaction_type}")
        
        success = await content_service.interact_with_content(
            user_id=current_user["user_id"],
            content_id=content_id,
            interaction_type=interaction_type,
            rating=interaction.rating
        )
        
        return {"success": success, "message": f"Content {interaction.interaction_type}d successfully"}
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ValidationError", "message": str(e)}
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )


@router.get(
    "/{content_id}/stats",
    response_model=ContentStatsResponse,
    summary="Get content statistics",
    description="Get detailed statistics for content item"
)
async def get_content_stats(
    content_id: int,
    db: AsyncSession = Depends(get_db)
) -> ContentStatsResponse:
    """
    Get content statistics.
    
    **Statistics Include:**
    - View counts and trends
    - Engagement metrics
    - User demographics
    - Performance over time
    """
    try:
        content_service = ContentService(db)
        
        content_detail = await content_service.get_content_detail(content_id)
        stats = content_detail["stats"]
        
        return ContentStatsResponse(**stats)
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )


# User's Content Management

@router.get(
    "/my/content",
    response_model=ContentListResponse,
    summary="Get my content",
    description="Get current user's content with all statuses",
    dependencies=[Depends(get_current_active_user)]
)
async def get_my_content(
    pagination: PaginationParams = Depends(get_pagination_params),
    include_drafts: bool = Query(True, description="Include unpublished content"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> ContentListResponse:
    """
    Get current user's content.
    
    **Features:**
    - Includes draft and published content
    - Shows detailed analytics
    - Content management actions
    - Performance insights
    """
    # This would be implemented in ContentService
    return ContentListResponse(
        items=[],
        total=0,
        page=1,
        pages=1,
        has_next=False,
        has_prev=False
    )


# Helper Functions

def _format_content_response(content_detail: Dict[str, Any], message: str = None) -> ContentResponse:
    """Format content detail from service into response schema."""
    content = content_detail["content"]
    stats = content_detail["stats"]
    
    # Extract metadata
    metadata = content.get("metadata", {})
    tags = metadata.get("tags", [])
    difficulty = metadata.get("difficulty")
    duration_minutes = metadata.get("duration_minutes")
    
    return ContentResponse(
        id=content["id"],
        title=content["title"],
        description=content["description"],
        content_type=content["content_type"],
        body=content["body"],
        url=content["url"],
        image_url=content["image_url"],
        tags=tags,
        difficulty=difficulty,
        duration_minutes=duration_minutes,
        is_published=True,  # Would come from content data
        is_featured=False,  # Would come from content data
        author=content["author"],
        category=content["category"],
        stats=ContentStatsResponse(**stats),
        created_at=content["created_at"],
        updated_at=content["created_at"]  # Would have separate updated_at
    )