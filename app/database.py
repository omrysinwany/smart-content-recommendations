"""
Database configuration and session management.

This module sets up:
1. Async SQLAlchemy engine for high performance
2. Session management for database operations
3. Base model with common functionality
4. Connection pooling for production use
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from typing import AsyncGenerator
from datetime import datetime

from app.config import settings


class Base(DeclarativeBase):
    """
    Base model class for all database models.
    
    Provides common functionality that all models should have:
    - Primary key (id)
    - Created/updated timestamps
    - String representation
    """
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"<{self.__class__.__name__}(id={self.id})>"


# Create async engine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,  # Log SQL queries in debug mode
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    
    This is used in FastAPI endpoints to get a database session:
    
    @app.get("/users")
    async def get_users(db: AsyncSession = Depends(get_db)):
        # Use db here
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables"""
    async with engine.begin() as conn:
        # Import all models here to ensure they're registered
        from app.models import user, content, interaction  # noqa
        await conn.run_sync(Base.metadata.create_all)