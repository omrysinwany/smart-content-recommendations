"""
User Repository - Specialized data access for User model.

This provides:
1. User-specific queries (by email, active users, etc.)
2. User relationship queries (followers, following)
3. User statistics and analytics queries
4. Authentication-related queries
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interaction import Follow
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    User-specific repository extending BaseRepository.

    This demonstrates how to extend the base repository
    with model-specific functionality.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        This is essential for authentication - users log in with email.

        Args:
            email: User's email address

        Returns:
            User instance or None if not found
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all active users.

        Useful for:
        - Admin dashboards
        - User recommendation systems
        - Analytics

        Args:
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of active users
        """
        result = await self.db.execute(
            select(User).where(User.is_active == True).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_with_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user with comprehensive statistics.

        This demonstrates complex queries with aggregations.
        Used for user profile pages and analytics.

        Args:
            user_id: User's primary key

        Returns:
            Dictionary with user data and statistics
        """
        # Main user query
        user_result = await self.db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            return None

        # Get follower count
        follower_count_result = await self.db.execute(
            select(func.count(Follow.id)).where(Follow.followed_id == user_id)
        )
        follower_count = follower_count_result.scalar() or 0

        # Get following count
        following_count_result = await self.db.execute(
            select(func.count(Follow.id)).where(Follow.follower_id == user_id)
        )
        following_count = following_count_result.scalar() or 0

        # Get content count - simplified to avoid lazy loading issues
        content_count = 0  # Will implement when needed

        return {
            "user": user,
            "stats": {
                "follower_count": follower_count,
                "following_count": following_count,
                "content_count": content_count,
                "total_interactions": user.total_interactions,
            },
        }

    async def search_users(
        self, query: str, skip: int = 0, limit: int = 20
    ) -> List[User]:
        """
        Search users by name or email.

        Demonstrates text search functionality.
        In production, you might use PostgreSQL full-text search.

        Args:
            query: Search term
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of matching users
        """
        search_term = f"%{query.lower()}%"

        result = await self.db.execute(
            select(User)
            .where(
                and_(
                    User.is_active == True,
                    or_(
                        func.lower(User.full_name).contains(search_term),
                        func.lower(User.email).contains(search_term),
                    ),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_followers(
        self, user_id: int, skip: int = 0, limit: int = 50
    ) -> List[User]:
        """
        Get users who follow this user.

        Demonstrates JOIN queries through relationships.

        Args:
            user_id: Target user's ID
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of follower users
        """
        result = await self.db.execute(
            select(User)
            .join(Follow, Follow.follower_id == User.id)
            .where(Follow.followed_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_following(
        self, user_id: int, skip: int = 0, limit: int = 50
    ) -> List[User]:
        """
        Get users that this user follows.

        Args:
            user_id: Current user's ID
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of users being followed
        """
        result = await self.db.execute(
            select(User)
            .join(Follow, Follow.followed_id == User.id)
            .where(Follow.follower_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def is_following(self, follower_id: int, followed_id: int) -> bool:
        """
        Check if one user follows another.

        Args:
            follower_id: ID of the potential follower
            followed_id: ID of the user being potentially followed

        Returns:
            True if following relationship exists
        """
        result = await self.db.execute(
            select(Follow).where(
                and_(
                    Follow.follower_id == follower_id, Follow.followed_id == followed_id
                )
            )
        )
        return result.first() is not None

    async def follow_user(self, follower_id: int, followed_id: int) -> bool:
        """
        Create a follow relationship.

        Args:
            follower_id: ID of the user who wants to follow
            followed_id: ID of the user to be followed

        Returns:
            True if follow was created, False if already exists
        """
        # Check if already following
        if await self.is_following(follower_id, followed_id):
            return False

        # Create follow relationship
        follow = Follow(follower_id=follower_id, followed_id=followed_id)
        self.db.add(follow)
        await self.db.commit()
        return True

    async def unfollow_user(self, follower_id: int, followed_id: int) -> bool:
        """
        Remove a follow relationship.

        Args:
            follower_id: ID of the user who wants to unfollow
            followed_id: ID of the user to be unfollowed

        Returns:
            True if unfollow was successful, False if wasn't following
        """
        result = await self.db.execute(
            select(Follow).where(
                and_(
                    Follow.follower_id == follower_id, Follow.followed_id == followed_id
                )
            )
        )
        follow = result.scalar_one_or_none()

        if not follow:
            return False

        await self.db.delete(follow)
        await self.db.commit()
        return True
