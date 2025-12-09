#!/usr/bin/env python3
"""
Seed database with initial data for testing and development.
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.security import get_password_hash
from app.models.content import Content, ContentCategory, ContentType
from app.models.user import User


async def seed_data():
    """Seed the database with initial data."""
    print("🌱 Starting database seeding...")

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        try:
            # 1. Create Test User
            print("👤 Checking test user...")
            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    email="test@example.com",
                    username="testuser",
                    full_name="Test User",
                    hashed_password=get_password_hash("testpass123"),
                    is_active=True,
                    is_verified=True,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                print(f"✅ Created test user (ID: {user.id})")
            else:
                print(f"ℹ️  Test user already exists (ID: {user.id})")

            # 2. Create Categories
            print("📂 Checking categories...")
            categories_data = [
                {
                    "name": "Technology",
                    "slug": "technology",
                    "description": "Tech news and tutorials",
                },
                {
                    "name": "Data Science",
                    "slug": "data-science",
                    "description": "AI, ML, and Big Data",
                },
                {
                    "name": "Web Development",
                    "slug": "web-development",
                    "description": "Frontend and Backend development",
                },
                {
                    "name": "DevOps",
                    "slug": "devops",
                    "description": "Cloud, CI/CD, and Infrastructure",
                },
                {
                    "name": "Career",
                    "slug": "career",
                    "description": "Career advice and growth",
                },
            ]

            categories = {}
            for cat_data in categories_data:
                result = await session.execute(
                    select(ContentCategory).where(
                        ContentCategory.slug == cat_data["slug"]
                    )
                )
                category = result.scalar_one_or_none()

                if not category:
                    category = ContentCategory(**cat_data)
                    session.add(category)
                    await session.commit()
                    await session.refresh(category)
                    print(f"✅ Created category: {category.name}")

                categories[category.slug] = category

            # 3. Create Content
            print("📚 Checking content...")

            # Sample content data
            content_samples = [
                {
                    "title": "The Future of AI in 2024",
                    "description": "An in-depth look at how Artificial Intelligence will shape the coming year, from LLMs to autonomous agents.",
                    "content_type": ContentType.ARTICLE,
                    "category_slug": "data-science",
                    "tags": ["AI", "Future", "Trends"],
                    "difficulty": "Intermediate",
                },
                {
                    "title": "Top 10 Python Frameworks",
                    "description": "A comprehensive comparison of the most popular Python frameworks for web development and data science.",
                    "content_type": ContentType.ARTICLE,
                    "category_slug": "technology",
                    "tags": ["Python", "Frameworks", "Programming"],
                    "difficulty": "Beginner",
                },
                {
                    "title": "Mastering React Hooks",
                    "description": "Learn how to effectively use React Hooks to build modern, functional components.",
                    "content_type": ContentType.VIDEO,
                    "category_slug": "web-development",
                    "tags": ["React", "Frontend", "JavaScript"],
                    "difficulty": "Advanced",
                },
                {
                    "title": "Introduction to Kubernetes",
                    "description": "Getting started with container orchestration using Kubernetes. A step-by-step guide.",
                    "content_type": ContentType.TUTORIAL,
                    "category_slug": "devops",
                    "tags": ["Kubernetes", "Docker", "DevOps"],
                    "difficulty": "Intermediate",
                },
                {
                    "title": "Ace Your Coding Interview",
                    "description": "Tips and tricks to crack technical interviews at top tech companies.",
                    "content_type": ContentType.ARTICLE,
                    "category_slug": "career",
                    "tags": ["Interview", "Career", "Coding"],
                    "difficulty": "Beginner",
                },
                {
                    "title": "Building Microservices with FastAPI",
                    "description": "How to design and implement scalable microservices using Python and FastAPI.",
                    "content_type": ContentType.COURSE,
                    "category_slug": "web-development",
                    "tags": ["FastAPI", "Microservices", "Python"],
                    "difficulty": "Advanced",
                },
            ]

            count = 0
            for item in content_samples:
                # Check if content exists
                result = await session.execute(
                    select(Content).where(Content.title == item["title"])
                )
                if result.scalar_one_or_none():
                    continue

                category = categories.get(item["category_slug"])
                if not category:
                    continue

                content = Content(
                    title=item["title"],
                    description=item["description"],
                    content_type=item["content_type"],
                    category_id=category.id,
                    author_id=user.id,
                    is_published=True,
                    content_metadata={
                        "tags": item["tags"],
                        "difficulty": item["difficulty"],
                        "duration_minutes": random.randint(5, 60),
                    },
                    view_count=random.randint(100, 10000),
                    like_count=random.randint(10, 1000),
                    trending_score=random.uniform(0, 100),
                )
                session.add(content)
                count += 1

            if count > 0:
                await session.commit()
                print(f"✅ Added {count} new content items")
            else:
                print("ℹ️  Content already seeded")

            print("✨ Seeding completed successfully!")

        except Exception as e:
            print(f"❌ Error during seeding: {e}")
            await session.rollback()
            raise

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())
