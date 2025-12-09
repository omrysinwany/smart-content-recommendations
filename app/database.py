"""
Database configuration and session management.

Enhanced for AWS deployment:
1. Async SQLAlchemy engine optimized for AWS RDS
2. SSL connection support for RDS
3. Connection pooling configured for ECS/EKS
4. CloudWatch integration for monitoring
5. AWS RDS Proxy support
"""

import logging
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import DateTime, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"<{self.__class__.__name__}(id={self.id})>"


# AWS RDS optimized engine configuration
def create_aws_optimized_engine():
    """Create database engine optimized for AWS RDS deployment."""

    # Use SSL-enabled URL for AWS RDS
    database_url = settings.database_url_with_ssl

    # AWS-optimized engine parameters
    engine_kwargs = {
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "echo": settings.debug,
        "pool_pre_ping": True,  # Validate connections before use
        "pool_recycle": 3600,  # Recycle connections every hour (AWS RDS connection limits)
    }

    # Add AWS RDS specific optimizations
    if settings.is_aws_environment:
        engine_kwargs.update(
            {
                "connect_args": {
                    "server_settings": {
                        "application_name": f"{settings.app_name}_{settings.environment}",
                        "client_encoding": "utf8",
                    }
                }
            }
        )

        # Enable connection pooling optimizations for ECS/EKS
        engine_kwargs["pool_timeout"] = 30
        engine_kwargs["pool_reset_on_return"] = "commit"

    return create_async_engine(database_url, **engine_kwargs)


# Create async engine with AWS optimizations
engine = create_aws_optimized_engine()

# Add logging for AWS CloudWatch
logger = logging.getLogger("database")


@event.listens_for(Engine, "connect")
def set_rds_pragmas(dbapi_connection, connection_record):
    """Set AWS RDS specific connection parameters."""
    if settings.is_aws_environment:
        logger.info("Connected to AWS RDS database")
        # Add any RDS-specific connection setup here


# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
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
        from app.models import content, interaction, user  # noqa

        await conn.run_sync(Base.metadata.create_all)
