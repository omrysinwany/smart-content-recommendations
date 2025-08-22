"""
API v1 router - Combines all API endpoints.

This provides:
1. Centralized API routing
2. Consistent API structure
3. Version management
4. Route organization
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, content, categories
from app.api.routes import recommendations
# Import other endpoint modules as we create them
# from app.api.v1.endpoints import users

# Create the main API router for version 1
api_router = APIRouter(prefix="/v1")

# Include all endpoint routers
api_router.include_router(auth.router)
api_router.include_router(content.router)
api_router.include_router(categories.router)
api_router.include_router(recommendations.router)

# We'll add these as we create them:
# api_router.include_router(users.router)

# API metadata for documentation
tags_metadata = [
    {
        "name": "Authentication",
        "description": "User authentication and authorization operations",
        "externalDocs": {
            "description": "Auth documentation",
            "url": "https://fastapi.tiangolo.com/tutorial/security/",
        },
    },
    {
        "name": "Users",
        "description": "User management and profile operations",
    },
    {
        "name": "Content",
        "description": "Content creation, management, and discovery",
    },
    {
        "name": "Recommendations",
        "description": "Content recommendation algorithms and personalization",
    },
    {
        "name": "Analytics",
        "description": "Usage analytics and statistics",
    },
]