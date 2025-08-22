"""
FastAPI dependencies for dependency injection.

This provides:
1. Service layer dependency injection
2. Repository dependency injection
3. Common utility dependencies
4. Request context dependencies
"""

from typing import Generator, Dict, Any
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.content_service import ContentService
from app.repositories.user_repository import UserRepository
from app.repositories.content_repository import ContentRepository
from app.core.security import get_current_active_user
from app.models.user import User


# Service Dependencies
def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Get AuthService instance with database session."""
    return AuthService(db)


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Get UserService instance with database session."""
    return UserService(db)


def get_content_service(db: AsyncSession = Depends(get_db)) -> ContentService:
    """Get ContentService instance with database session."""
    return ContentService(db)


# Repository Dependencies
def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """Get UserRepository instance with database session."""
    return UserRepository(db)


def get_content_repository(db: AsyncSession = Depends(get_db)) -> ContentRepository:
    """Get ContentRepository instance with database session."""
    return ContentRepository(db)


# Utility Dependencies
def get_request_context(request: Request) -> Dict[str, Any]:
    """
    Extract useful context from the request.
    
    Returns:
        Dictionary with request context information
    """
    return {
        "request_id": getattr(request.state, "request_id", None),
        "user_agent": request.headers.get("user-agent"),
        "client_ip": request.client.host if request.client else None,
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers)
    }


# Common pagination dependency
class PaginationParams:
    """Pagination parameters for list endpoints."""
    
    def __init__(self, skip: int = 0, limit: int = 20):
        self.skip = max(0, skip)  # Ensure skip is not negative
        self.limit = min(max(1, limit), 100)  # Limit between 1 and 100


def get_pagination_params(
    skip: int = 0,
    limit: int = 20
) -> PaginationParams:
    """
    Get pagination parameters with validation.
    
    Args:
        skip: Number of items to skip (default: 0)
        limit: Maximum items to return (default: 20, max: 100)
        
    Returns:
        Validated pagination parameters
    """
    return PaginationParams(skip, limit)


# Search parameters dependency
class SearchParams:
    """Search parameters for search endpoints."""
    
    def __init__(
        self,
        q: str = "",
        category: str = None,
        content_type: str = None,
        sort_by: str = "created_at",
        order: str = "desc"
    ):
        self.query = q.strip()
        self.category = category
        self.content_type = content_type
        self.sort_by = sort_by
        self.order = order.lower()


def get_search_params(
    q: str = "",
    category: str = None,
    content_type: str = None,
    sort_by: str = "created_at",
    order: str = "desc"
) -> SearchParams:
    """
    Get search parameters with validation.
    
    Args:
        q: Search query string
        category: Content category filter
        content_type: Content type filter
        sort_by: Sort field (default: created_at)
        order: Sort order (asc/desc, default: desc)
        
    Returns:
        Validated search parameters
    """
    return SearchParams(q, category, content_type, sort_by, order)


# Current user dependencies
async def get_current_user(
    token_data: Dict[str, Any] = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
) -> User:
    """
    Get current user from JWT token.
    
    Args:
        token_data: Token data from JWT validation
        user_service: User service for database operations
        
    Returns:
        Current user object
    """
    user = await user_service.get_user_by_id(token_data["user_id"])
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User not found")
    return user


# Current user with extended info
async def get_current_user_extended(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> Dict[str, Any]:
    """
    Get current user with extended profile information.
    
    Args:
        current_user: Current user object
        user_service: User service for database operations
        
    Returns:
        Extended user information
    """
    user_profile = await user_service.get_user_profile(current_user.id)
    
    return {
        "user": current_user,
        "profile": user_profile
    }