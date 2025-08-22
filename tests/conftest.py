"""
Shared test fixtures and configuration.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.user import User
from app.models.content import Content, ContentCategory
from app.models.interaction import Interaction
from app.algorithms.base import RecommendationResult


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture 
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    return redis_mock


@pytest.fixture
async def test_db():
    """Create test database with in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with SessionLocal() as session:
        yield session
        
    await engine.dispose()


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    return User(
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$hashedpassword",
        is_active=True
    )


@pytest.fixture
def sample_content():
    """Sample content for testing."""
    return Content(
        title="Test Article",
        description="A test article about Python",
        content_type="article",
        body="This is test content about Python programming.",
        author_id=1,
        content_metadata={"tags": ["python", "programming"], "difficulty": "beginner"}
    )


@pytest.fixture
def sample_recommendation_result():
    """Sample recommendation result for testing."""
    return RecommendationResult(
        content_ids=[1, 2, 3, 4, 5],
        scores=[0.95, 0.87, 0.82, 0.78, 0.75],
        algorithm_name="Test Algorithm",
        user_id=1,
        metadata={"test": True}
    )


@pytest.fixture
def mock_recommendation_service(mock_db):
    """Mock recommendation service with common responses."""
    from app.services.recommendation_service import RecommendationService
    service = RecommendationService(mock_db)
    
    # Mock common methods
    service.interaction_repo.get_user_recommendation_data = AsyncMock(return_value={
        "total_interactions": 10,
        "preferred_content_types": ["article", "video"],
        "interaction_summary": {"likes": 5, "views": 20, "saves": 3}
    })
    
    return service


@pytest.fixture
def mock_cache_manager(mock_redis):
    """Mock cache manager for testing."""
    from app.core.cache import CacheManager
    cache = CacheManager()
    cache.redis_client = mock_redis
    return cache