#!/usr/bin/env python3
"""
Create test user for recommendation testing
"""

import asyncio
import os
import sys

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.security import get_password_hash
from app.models.user import User


async def create_test_user():
    """Create a test user for API testing."""

    settings = get_settings()

    # Create database engine
    engine = create_async_engine(settings.DATABASE_URL)

    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        try:
            # Check if test user already exists
            from sqlalchemy import select

            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"✅ Test user already exists!")
                print(f"   Email: test@example.com")
                print(f"   Password: testpass123")
                print(f"   User ID: {existing_user.id}")
                return

            # Create new test user
            test_user = User(
                email="test@example.com",
                username="testuser",
                full_name="Test User",
                hashed_password=get_password_hash("testpass123"),
                is_active=True,
                is_verified=True,
            )

            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)

            print(f"🎉 Test user created successfully!")
            print(f"   Email: test@example.com")
            print(f"   Password: testpass123")
            print(f"   User ID: {test_user.id}")
            print(f"   Username: testuser")

        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            await session.rollback()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_test_user())
