"""
Interaction Repository - Data access for user-content interactions.

This provides:
1. Interaction CRUD operations
2. User interaction history
3. Content engagement analytics
4. Interaction aggregation queries
5. Recommendation data preparation
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Content
from app.models.interaction import Interaction, InteractionType
from app.models.user import User
from app.repositories.base import BaseRepository


class InteractionRepository(BaseRepository[Interaction]):
    """
    Interaction-specific repository with analytics capabilities.

    This demonstrates advanced data analytics patterns:
    - Aggregation queries for recommendations
    - User behavior analysis
    - Content performance metrics
    - Time-series interaction data
    """

    def __init__(self, db: AsyncSession):
        super().__init__(Interaction, db)

    async def create_or_update_interaction(
        self,
        user_id: int,
        content_id: int,
        interaction_type: InteractionType,
        rating: Optional[float] = None,
    ) -> Interaction:
        """
        Create or update user interaction with content.

        This handles the business logic of:
        - Creating new interactions
        - Updating existing interactions (e.g., changing rating)
        - Preventing duplicate interactions of same type

        Args:
            user_id: User performing interaction
            content_id: Content being interacted with
            interaction_type: Type of interaction
            rating: Optional rating (for RATE interactions)

        Returns:
            Interaction record
        """
        # Check if interaction already exists
        existing_result = await self.db.execute(
            select(Interaction).where(
                and_(
                    Interaction.user_id == user_id,
                    Interaction.content_id == content_id,
                    Interaction.interaction_type == interaction_type,
                )
            )
        )
        existing_interaction = existing_result.scalar_one_or_none()

        if existing_interaction:
            # Update existing interaction
            if rating is not None:
                existing_interaction.rating = rating
                existing_interaction.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(existing_interaction)
            return existing_interaction
        else:
            # Create new interaction
            interaction = Interaction(
                user_id=user_id,
                content_id=content_id,
                interaction_type=interaction_type,
                rating=rating,
            )
            self.db.add(interaction)
            await self.db.commit()
            await self.db.refresh(interaction)
            return interaction

    async def get_user_interactions(
        self,
        user_id: int,
        interaction_types: Optional[List[InteractionType]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Interaction]:
        """
        Get user's interaction history.

        Args:
            user_id: User ID
            interaction_types: Filter by interaction types
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of user interactions with content details
        """
        query = (
            select(Interaction)
            .options(selectinload(Interaction.content))
            .where(Interaction.user_id == user_id)
        )

        if interaction_types:
            query = query.where(Interaction.interaction_type.in_(interaction_types))

        query = query.order_by(desc(Interaction.created_at)).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_content_interactions(
        self, content_id: int, interaction_types: Optional[List[InteractionType]] = None
    ) -> List[Interaction]:
        """
        Get all interactions for specific content.

        Args:
            content_id: Content ID
            interaction_types: Filter by interaction types

        Returns:
            List of interactions for the content
        """
        query = select(Interaction).where(Interaction.content_id == content_id)

        if interaction_types:
            query = query.where(Interaction.interaction_type.in_(interaction_types))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_interaction_stats(self, content_id: int) -> Dict[str, Any]:
        """
        Get aggregated interaction statistics for content.

        Args:
            content_id: Content ID

        Returns:
            Dictionary with interaction counts and metrics
        """
        # Get interaction counts by type
        stats_result = await self.db.execute(
            select(
                Interaction.interaction_type,
                func.count(Interaction.id).label("count"),
                func.avg(Interaction.rating).label("avg_rating"),
            )
            .where(Interaction.content_id == content_id)
            .group_by(Interaction.interaction_type)
        )

        stats = {}
        total_ratings = 0
        rating_sum = 0

        for stat in stats_result.all():
            interaction_type = stat.interaction_type
            count = stat.count
            avg_rating = stat.avg_rating

            stats[f"{interaction_type.value}_count"] = count

            if interaction_type == InteractionType.RATE and avg_rating:
                stats["average_rating"] = float(avg_rating)
                stats["rating_count"] = count
                total_ratings = count
                rating_sum = float(avg_rating) * count

        # Calculate overall engagement score
        views = stats.get("view_count", 0)
        likes = stats.get("like_count", 0)
        saves = stats.get("save_count", 0)
        shares = stats.get("share_count", 0)

        if views > 0:
            engagement_rate = (likes + saves + shares) / views
        else:
            engagement_rate = 0.0

        stats.update(
            {
                "total_interactions": sum(
                    [stats.get(f"{t.value}_count", 0) for t in InteractionType]
                ),
                "engagement_rate": round(engagement_rate, 4),
            }
        )

        return stats

    async def get_user_content_interactions(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """
        Get specific user's interactions with specific content.

        Args:
            user_id: User ID
            content_id: Content ID

        Returns:
            Dictionary of user's interactions with the content
        """
        result = await self.db.execute(
            select(Interaction).where(
                and_(
                    Interaction.user_id == user_id, Interaction.content_id == content_id
                )
            )
        )
        interactions = result.scalars().all()

        user_interactions = {
            "has_viewed": False,
            "has_liked": False,
            "has_saved": False,
            "has_shared": False,
            "rating": None,
        }

        for interaction in interactions:
            if interaction.interaction_type == InteractionType.VIEW:
                user_interactions["has_viewed"] = True
            elif interaction.interaction_type == InteractionType.LIKE:
                user_interactions["has_liked"] = True
            elif interaction.interaction_type == InteractionType.SAVE:
                user_interactions["has_saved"] = True
            elif interaction.interaction_type == InteractionType.SHARE:
                user_interactions["has_shared"] = True
            elif interaction.interaction_type == InteractionType.RATE:
                user_interactions["rating"] = interaction.rating

        return user_interactions

    async def get_similar_users(
        self, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find users with similar interaction patterns.

        This is used for collaborative filtering recommendations.

        Args:
            user_id: Target user ID
            limit: Maximum similar users to return

        Returns:
            List of similar users with similarity scores
        """
        # Get user's liked content
        user_likes_result = await self.db.execute(
            select(Interaction.content_id).where(
                and_(
                    Interaction.user_id == user_id,
                    Interaction.interaction_type == InteractionType.LIKE,
                )
            )
        )
        user_liked_content = [row[0] for row in user_likes_result.all()]

        if not user_liked_content:
            return []

        # Find users who liked similar content
        similar_users_result = await self.db.execute(
            select(
                Interaction.user_id, func.count(Interaction.id).label("common_likes")
            )
            .where(
                and_(
                    Interaction.user_id != user_id,
                    Interaction.interaction_type == InteractionType.LIKE,
                    Interaction.content_id.in_(user_liked_content),
                )
            )
            .group_by(Interaction.user_id)
            .having(func.count(Interaction.id) >= 2)  # At least 2 common likes
            .order_by(desc(func.count(Interaction.id)))
            .limit(limit)
        )

        similar_users = []
        for row in similar_users_result.all():
            similarity_score = row.common_likes / len(user_liked_content)
            similar_users.append(
                {
                    "user_id": row.user_id,
                    "common_likes": row.common_likes,
                    "similarity_score": round(similarity_score, 4),
                }
            )

        return similar_users

    async def get_trending_content_ids(
        self, days: int = 7, limit: int = 100
    ) -> List[int]:
        """
        Get content IDs trending based on recent interactions.

        Args:
            days: Number of days to look back
            limit: Maximum content IDs to return

        Returns:
            List of content IDs ordered by trending score
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(
                Interaction.content_id,
                # Weighted scoring: likes=3, saves=2, shares=5, views=1
                func.sum(
                    func.case(
                        (Interaction.interaction_type == InteractionType.LIKE, 3),
                        (Interaction.interaction_type == InteractionType.SAVE, 2),
                        (Interaction.interaction_type == InteractionType.SHARE, 5),
                        (Interaction.interaction_type == InteractionType.VIEW, 1),
                        else_=0,
                    )
                ).label("trending_score"),
            )
            .where(Interaction.created_at >= cutoff_date)
            .group_by(Interaction.content_id)
            .having(func.count(Interaction.id) >= 5)  # Minimum interactions
            .order_by(desc("trending_score"))
            .limit(limit)
        )

        return [row.content_id for row in result.all()]

    async def get_user_recommendation_data(self, user_id: int) -> Dict[str, Any]:
        """
        Get user data for recommendation algorithms.

        Args:
            user_id: User ID

        Returns:
            Dictionary with user preference data
        """
        # Get user's interaction summary
        interactions_result = await self.db.execute(
            select(
                Interaction.interaction_type, func.count(Interaction.id).label("count")
            )
            .where(Interaction.user_id == user_id)
            .group_by(Interaction.interaction_type)
        )

        interaction_summary = {}
        for row in interactions_result.all():
            interaction_summary[f"{row.interaction_type.value}_count"] = row.count

        # Get user's preferred content types (based on interactions)
        content_types_result = await self.db.execute(
            select(
                Content.content_type,
                func.count(Interaction.id).label("interaction_count"),
            )
            .join(Content, Content.id == Interaction.content_id)
            .where(
                and_(
                    Interaction.user_id == user_id,
                    Interaction.interaction_type.in_(
                        [
                            InteractionType.LIKE,
                            InteractionType.SAVE,
                            InteractionType.RATE,
                        ]
                    ),
                )
            )
            .group_by(Content.content_type)
            .order_by(desc("interaction_count"))
        )

        preferred_content_types = [
            row.content_type for row in content_types_result.all()
        ]

        # Get user's preferred categories (based on interactions)
        categories_result = await self.db.execute(
            select(
                Content.category_id,
                func.count(Interaction.id).label("interaction_count"),
            )
            .join(Content, Content.id == Interaction.content_id)
            .where(
                and_(
                    Interaction.user_id == user_id,
                    Interaction.interaction_type.in_(
                        [
                            InteractionType.LIKE,
                            InteractionType.SAVE,
                            InteractionType.RATE,
                        ]
                    ),
                )
            )
            .group_by(Content.category_id)
            .order_by(desc("interaction_count"))
            .limit(10)
        )

        top_categories = [
            row.category_id for row in categories_result.all() if row.category_id
        ]

        return {
            "user_id": user_id,
            "interaction_summary": interaction_summary,
            "preferred_content_types": preferred_content_types,
            "top_categories": top_categories,
            "total_interactions": sum(interaction_summary.values()),
        }
