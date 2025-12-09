#!/usr/bin/env python3
"""
Simple script to run database migrations.
This can be used to create the database tables.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.database import Base, engine


async def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    print(f"Database URL: {settings.database_url}")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully!")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

    return True


if __name__ == "__main__":
    asyncio.run(create_tables())
