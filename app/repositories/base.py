"""
Base Repository - Generic repository with common CRUD operations.

This provides:
1. Generic CRUD operations for all models
2. Type safety with generics
3. Consistent interface across all repositories
4. Async database operations
"""

from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import Base

# Generic type for any database model
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing common CRUD operations.

    This is the foundation of our Repository pattern:
    - All specific repositories inherit from this
    - Provides type-safe operations
    - Consistent interface across the application
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        """
        Initialize repository with model type and database session.

        Args:
            model: The SQLAlchemy model class (User, Content, etc.)
            db: Async database session
        """
        self.model = model
        self.db = db

    async def create(self, obj_data: Dict[str, Any]) -> ModelType:
        """
        Create a new record.

        Args:
            obj_data: Dictionary of field values

        Returns:
            Created model instance
        """
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def get(self, id: int) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Primary key value

        Returns:
            Model instance or None if not found
        """
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, skip: int = 0, limit: int = 100, filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        Get multiple records with pagination and filtering.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            filters: Dictionary of field:value filters

        Returns:
            List of model instances
        """
        query = select(self.model)

        # Apply filters if provided
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, id: int, obj_data: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            id: Primary key value
            obj_data: Dictionary of fields to update

        Returns:
            Updated model instance or None if not found
        """
        # First check if record exists
        db_obj = await self.get(id)
        if not db_obj:
            return None

        # Update fields
        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        """
        Delete a record by ID.

        Args:
            id: Primary key value

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(delete(self.model).where(self.model.id == id))
        await self.db.commit()
        return result.rowcount > 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records with optional filters.

        Args:
            filters: Dictionary of field:value filters

        Returns:
            Number of matching records
        """
        query = select(func.count(self.model.id))

        # Apply filters if provided
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def exists(self, id: int) -> bool:
        """
        Check if record exists by ID.

        Args:
            id: Primary key value

        Returns:
            True if exists, False otherwise
        """
        result = await self.db.execute(select(self.model.id).where(self.model.id == id))
        return result.first() is not None
