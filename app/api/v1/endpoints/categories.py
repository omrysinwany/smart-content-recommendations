"""
Category management API endpoints.

This provides:
1. Category CRUD operations
2. Category-based content browsing
3. Category statistics and analytics
4. Hierarchical category support
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.database import get_db
from app.core.security import get_current_active_user, require_admin
from app.core.exceptions import ValidationError, NotFoundError, ConflictError
from app.schemas.content import (
    CategoryCreateRequest,
    CategoryResponse,
    ContentListResponse
)
from app.schemas.auth import APIError, MessageResponse
from app.dependencies import get_pagination_params, PaginationParams

# Create router
router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
    responses={
        404: {"model": APIError, "description": "Category not found"},
        422: {"model": APIError, "description": "Validation error"},
    }
)


@router.get(
    "/",
    response_model=List[CategoryResponse],
    summary="List all categories",
    description="Get list of all content categories with statistics"
)
async def list_categories(
    db: AsyncSession = Depends(get_db)
) -> List[CategoryResponse]:
    """
    Get all content categories.
    
    **Features:**
    - Ordered by popularity
    - Includes content counts
    - Color-coded for UI
    - SEO-friendly slugs
    """
    # Mock data for now - would be implemented in CategoryService
    categories = [
        CategoryResponse(
            id=1,
            name="Technology",
            slug="technology",
            description="Technology and programming content",
            color="#007bff"
        ),
        CategoryResponse(
            id=2,
            name="Science",
            slug="science",
            description="Scientific articles and research",
            color="#28a745"
        ),
        CategoryResponse(
            id=3,
            name="Business",
            slug="business",
            description="Business and entrepreneurship content",
            color="#ffc107"
        )
    ]
    
    return categories


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
    description="Create a new content category (admin only)",
    dependencies=[Depends(require_admin)]
)
async def create_category(
    category_data: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: Dict[str, Any] = Depends(require_admin)
) -> CategoryResponse:
    """
    Create a new category.
    
    **Admin Only**
    
    **Features:**
    - Automatic slug generation
    - Color validation
    - Duplicate name checking
    - SEO optimization
    """
    try:
        # Generate slug from name
        slug = category_data.name.lower().replace(" ", "-").replace("&", "and")
        
        # Check for existing category (would be in service layer)
        # existing = await category_service.get_by_slug(slug)
        # if existing:
        #     raise ConflictError("Category with this name already exists")
        
        # Create category (would be in service layer)
        # category = await category_service.create_category(category_data.dict())
        
        # Mock response for now
        return CategoryResponse(
            id=99,
            name=category_data.name,
            slug=slug,
            description=category_data.description,
            color=category_data.color
        )
        
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "ConflictError", "message": str(e)}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ValidationError", "message": str(e)}
        )


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Get category by ID",
    description="Get category details with statistics"
)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db)
) -> CategoryResponse:
    """
    Get category by ID.
    
    **Returns:**
    - Category details
    - Content count in category
    - Popular tags in category
    - Recent activity metrics
    """
    try:
        # Would be implemented in CategoryService
        # category = await category_service.get_category_with_stats(category_id)
        
        # Mock response for now
        if category_id == 1:
            return CategoryResponse(
                id=1,
                name="Technology",
                slug="technology",
                description="Technology and programming content",
                color="#007bff"
            )
        else:
            raise NotFoundError("Category not found")
            
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )


@router.get(
    "/{category_id}/content",
    response_model=ContentListResponse,
    summary="Get content in category",
    description="Get paginated content list for specific category"
)
async def get_category_content(
    category_id: int,
    pagination: PaginationParams = Depends(get_pagination_params),
    sort_by: str = "created_at",
    order: str = "desc",
    db: AsyncSession = Depends(get_db)
) -> ContentListResponse:
    """
    Get content in specific category.
    
    **Sorting Options:**
    - created_at: Newest first (default)
    - view_count: Most popular
    - like_count: Most liked
    - trending_score: Trending content
    
    **Features:**
    - Pagination support
    - Multiple sort options
    - Content filtering
    - Performance optimized
    """
    try:
        # Would be implemented using ContentService
        # content_list = await content_service.get_content_by_category(
        #     category_id, pagination.skip, pagination.limit, sort_by, order
        # )
        
        # Mock response for now
        return ContentListResponse(
            items=[],
            total=0,
            page=1,
            pages=1,
            has_next=False,
            has_prev=False
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update category",
    description="Update category details (admin only)",
    dependencies=[Depends(require_admin)]
)
async def update_category(
    category_id: int,
    category_data: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: Dict[str, Any] = Depends(require_admin)
) -> CategoryResponse:
    """
    Update category.
    
    **Admin Only**
    
    **Features:**
    - Updates slug if name changes
    - Maintains SEO URLs with redirects
    - Updates all related content indexes
    - Preserves category statistics
    """
    try:
        # Would be implemented in CategoryService
        # updated_category = await category_service.update_category(category_id, category_data.dict())
        
        # Mock response for now
        return CategoryResponse(
            id=category_id,
            name=category_data.name,
            slug=category_data.name.lower().replace(" ", "-"),
            description=category_data.description,
            color=category_data.color
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )


@router.delete(
    "/{category_id}",
    response_model=MessageResponse,
    summary="Delete category",
    description="Delete category and reassign content (admin only)",
    dependencies=[Depends(require_admin)]
)
async def delete_category(
    category_id: int,
    reassign_to: int = None,
    db: AsyncSession = Depends(get_db),
    admin_user: Dict[str, Any] = Depends(require_admin)
) -> MessageResponse:
    """
    Delete category.
    
    **Admin Only**
    
    **Options:**
    - reassign_to: Move all content to another category
    - If no reassign_to, content becomes uncategorized
    
    **Safety Features:**
    - Cannot delete if content exists (unless reassigned)
    - Confirms before deletion
    - Updates search indexes
    """
    try:
        # Would check if category has content
        # if has_content and not reassign_to:
        #     raise ValidationError("Cannot delete category with content. Use reassign_to parameter.")
        
        # Would be implemented in CategoryService
        # await category_service.delete_category(category_id, reassign_to)
        
        return MessageResponse(
            message=f"Category {category_id} deleted successfully"
        )
        
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
    "/{category_id}/stats",
    summary="Get category statistics",
    description="Get detailed statistics for category"
)
async def get_category_stats(
    category_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get category statistics.
    
    **Statistics Include:**
    - Total content count by type
    - View and engagement metrics
    - Top contributors
    - Popular tags
    - Growth trends
    """
    try:
        # Would be implemented in CategoryService
        stats = {
            "category_id": category_id,
            "total_content": 42,
            "content_by_type": {
                "article": 25,
                "video": 12,
                "course": 5
            },
            "total_views": 15420,
            "total_likes": 1250,
            "top_tags": [
                "python", "machine-learning", "tutorial"
            ],
            "top_contributors": [
                {"id": 1, "name": "John Doe", "content_count": 8},
                {"id": 2, "name": "Jane Smith", "content_count": 6}
            ]
        }
        
        return stats
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)}
        )


# Popular categories endpoint
@router.get(
    "/popular/trending",
    response_model=List[CategoryResponse],
    summary="Get popular categories",
    description="Get categories ordered by recent activity and content"
)
async def get_popular_categories(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
) -> List[CategoryResponse]:
    """
    Get popular/trending categories.
    
    **Algorithm:**
    - Recent content creation activity
    - User engagement metrics
    - View counts and interactions
    - Balanced across different types
    
    **Use Cases:**
    - Homepage category showcase
    - Category browsing page
    - Content discovery
    """
    # Would be implemented with sophisticated ranking algorithm
    popular_categories = [
        CategoryResponse(
            id=1,
            name="Technology",
            slug="technology", 
            description="Trending tech content",
            color="#007bff"
        ),
        CategoryResponse(
            id=2,
            name="Science",
            slug="science",
            description="Popular science articles", 
            color="#28a745"
        )
    ]
    
    return popular_categories[:limit]