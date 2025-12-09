"""
Repository layer - Data access patterns for the application.

This module exports all repositories for easy importing:
- BaseRepository: Generic CRUD operations
- UserRepository: User-specific data access
- ContentRepository: Content-specific data access
"""

from .base import BaseRepository
from .content_repository import ContentRepository
from .user_repository import UserRepository

__all__ = ["BaseRepository", "UserRepository", "ContentRepository"]
