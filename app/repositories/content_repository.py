"""
Content Repository - Specialized data access for Content model.

This provides:
1. Content discovery queries (trending, by category, by author)
2. Search functionality with filters
3. Content statistics and analytics
4. Recommendation-related queries
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Content, ContentCategory, ContentType
from app.models.interaction import Interaction, InteractionType
from app.models.user import User
from app.repositories.base import BaseRepository


class ContentRepository(BaseRepository[Content]):
    """
    Content-specific repository with advanced querying capabilities.

    This demonstrates complex database queries needed for
    content recommendation systems.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(Content, db)

    async def get_published_content(
        self, skip: int = 0, limit: int = 20
    ) -> List[Content]:
        """
        Get published content ordered by creation date.

        Args:
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of published content
        """
        result = await self.db.execute(
            select(Content)
            .where(Content.is_published == True)
            .order_by(desc(Content.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_trending_content(
        self, days: int = 7, skip: int = 0, limit: int = 20
    ) -> List[Content]:
        """
        Get trending content based on recent engagement.

        This demonstrates time-based queries and scoring algorithms.

        Args:
            days: Number of days to look back
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of trending content
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(Content)
            .where(
                and_(Content.is_published == True, Content.created_at >= cutoff_date)
            )
            .order_by(desc(Content.trending_score), desc(Content.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_content_by_category(
        self, category_id: int, skip: int = 0, limit: int = 20
    ) -> List[Content]:
        """
        Get content by category.

        Args:
            category_id: Category primary key
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of content in category
        """
        result = await self.db.execute(
            select(Content)
            .where(
                and_(Content.category_id == category_id, Content.is_published == True)
            )
            .order_by(desc(Content.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_content_by_author(
        self,
        author_id: int,
        include_unpublished: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Content]:
        """
        Get content by specific author.

        Args:
            author_id: Author's user ID
            include_unpublished: Whether to include draft content
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of author's content
        """
        query = select(Content).where(Content.author_id == author_id)

        if not include_unpublished:
            query = query.where(Content.is_published == True)

        result = await self.db.execute(
            query.order_by(desc(Content.created_at)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def search_content(
        self,
        search_query: str,
        content_type: Optional[ContentType] = None,
        category_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Content]:
        """
        Advanced content search with filters.

        This demonstrates complex filtering and text search.
        In production, you'd use PostgreSQL full-text search or Elasticsearch.

        Args:
            search_query: Text to search for
            content_type: Optional content type filter
            category_id: Optional category filter
            skip: Pagination offset
            limit: Maximum results

        Returns:
            List of matching content
        """
        search_term = f"%{search_query.lower()}%"

        query = select(Content).where(
            and_(
                Content.is_published == True,
                or_(
                    func.lower(Content.title).contains(search_term),
                    func.lower(Content.description).contains(search_term),
                ),
            )
        )

        # Apply filters
        if content_type:
            query = query.where(Content.content_type == content_type)

        if category_id:
            query = query.where(Content.category_id == category_id)

        result = await self.db.execute(
            query.order_by(desc(Content.created_at)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_content_with_stats(self, content_id: int) -> Optional[Dict[str, Any]]:
        """
        Get content with comprehensive statistics.

        This demonstrates complex aggregation queries.

        Args:
            content_id: Content primary key

        Returns:
            Dictionary with content and statistics
        """
        # Get content
        content_result = await self.db.execute(
            select(Content)
            .options(selectinload(Content.author))
            .options(selectinload(Content.category))
            .where(Content.id == content_id)
        )
        content = content_result.scalar_one_or_none()

        if not content:
            return None

        # Get interaction statistics
        stats_result = await self.db.execute(
            select(
                Interaction.interaction_type, func.count(Interaction.id).label("count")
            )
            .where(Interaction.content_id == content_id)
            .group_by(Interaction.interaction_type)
        )

        # Convert to dictionary
        interaction_stats = {
            stat.interaction_type: stat.count for stat in stats_result.all()
        }

        return {
            "content": content,
            "stats": {
                "views": interaction_stats.get(InteractionType.VIEW, 0),
                "likes": interaction_stats.get(InteractionType.LIKE, 0),
                "saves": interaction_stats.get(InteractionType.SAVE, 0),
                "shares": interaction_stats.get(InteractionType.SHARE, 0),
                "engagement_rate": content.engagement_rate,
            },
        }

    async def get_similar_content(
        self, content_id: int, limit: int = 5
    ) -> List[Content]:
        """
        Get content similar to given content.

        This is a simplified version - in practice, you'd use
        machine learning algorithms for better similarity.

        Args:
            content_id: Reference content ID
            limit: Maximum similar content to return

        Returns:
            List of similar content
        """
        # Get the reference content
        reference_result = await self.db.execute(
            select(Content).where(Content.id == content_id)
        )
        reference_content = reference_result.scalar_one_or_none()

        if not reference_content:
            return []

        # Find similar content by category and type
        result = await self.db.execute(
            select(Content)
            .where(
                and_(
                    Content.id != content_id,  # Exclude the reference content
                    Content.is_published == True,
                    or_(
                        Content.category_id == reference_content.category_id,
                        Content.content_type == reference_content.content_type,
                    ),
                )
            )
            .order_by(desc(Content.trending_score))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_content_stats(self, content_id: int) -> bool:
        """
        Update content statistics from interactions.

        This would typically be called by a background job.

        Args:
            content_id: Content to update

        Returns:
            True if update was successful
        """
        # Get interaction counts
        stats_result = await self.db.execute(
            select(
                func.count(Interaction.id)
                .filter(Interaction.interaction_type == InteractionType.VIEW)
                .label("views"),
                func.count(Interaction.id)
                .filter(Interaction.interaction_type == InteractionType.LIKE)
                .label("likes"),
                func.count(Interaction.id)
                .filter(Interaction.interaction_type == InteractionType.SAVE)
                .label("saves"),
                func.count(Interaction.id)
                .filter(Interaction.interaction_type == InteractionType.SHARE)
                .label("shares"),
            ).where(Interaction.content_id == content_id)
        )

        stats = stats_result.first()
        if not stats:
            return False

        # Calculate trending score (simple algorithm)
        # In production, you'd use more sophisticated algorithms
        days_old = (datetime.utcnow() - datetime.now()).days + 1
        trending_score = (
            stats.likes * 3 + stats.saves * 2 + stats.shares * 5 + stats.views
        ) / max(days_old, 1)

        # Update content
        await self.db.execute(
            text(
                """
                UPDATE contents 
                SET view_count = :views,
                    like_count = :likes,
                    save_count = :saves,
                    share_count = :shares,
                    trending_score = :trending_score
                WHERE id = :content_id
            """
            ),
            {
                "views": stats.views,
                "likes": stats.likes,
                "saves": stats.saves,
                "shares": stats.shares,
                "trending_score": trending_score,
                "content_id": content_id,
            },
        )

        await self.db.commit()
        return True

    async def get_content_for_recommendations(
        self,
        exclude_user_id: Optional[int] = None,
        exclude_content_ids: Optional[List[int]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get content suitable for recommendations.

        Args:
            exclude_user_id: User ID to exclude their own content
            exclude_content_ids: Content IDs to exclude
            limit: Maximum content to return

        Returns:
            List of content dictionaries for recommendations
        """
        query = select(Content).where(Content.is_published == True)

        # Exclude user's own content
        if exclude_user_id:
            query = query.where(Content.author_id != exclude_user_id)

        # Exclude specific content
        if exclude_content_ids:
            query = query.where(~Content.id.in_(exclude_content_ids))

        # Order by trending score and recency
        query = query.order_by(
            desc(Content.trending_score), desc(Content.created_at)
        ).limit(limit)

        result = await self.db.execute(query)
        content_items = result.scalars().all()

        # Convert to dictionaries for algorithm processing
        content_dicts = []
        for content in content_items:
            content_dict = {
                "id": content.id,
                "title": content.title,
                "description": content.description,
                "content_type": content.content_type,
                "category_id": content.category_id,
                "content_metadata": content.content_metadata or {},
                "author_id": content.author_id,
                "created_at": (
                    content.created_at.isoformat() if content.created_at else None
                ),
                "trending_score": content.trending_score,
            }
            content_dicts.append(content_dict)

        return content_dicts

    async def list_content_with_filters(
        self,
        content_type: Optional[str] = None,
        category_id: Optional[int] = None,
        author_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc",
        skip: int = 0,
        limit: int = 20,
        include_stats: bool = False,
    ) -> Dict[str, Any]:
        """
        List content with comprehensive filtering and sorting options.

        Args:
            content_type: Filter by content type
            category_id: Filter by category ID
            author_id: Filter by author ID
            tags: Filter by tags (AND operation)
            difficulty: Filter by difficulty level
            sort_by: Field to sort by (created_at, updated_at, view_count, like_count, trending_score)
            order: Sort order (asc/desc)
            skip: Pagination offset
            limit: Maximum results
            include_stats: Whether to include interaction statistics

        Returns:
            Dictionary with content items and total count
        """
        # Build base query
        query = (
            select(Content)
            .options(selectinload(Content.author), selectinload(Content.category))
            .where(Content.is_published == True)
        )

        # Apply filters
        if content_type:
            try:
                content_type_enum = ContentType(content_type.upper())
                query = query.where(Content.content_type == content_type_enum)
            except ValueError:
                pass  # Invalid content type, skip filter

        if category_id:
            query = query.where(Content.category_id == category_id)

        if author_id:
            query = query.where(Content.author_id == author_id)

        if difficulty:
            # Check if difficulty is in metadata
            query = query.where(
                func.json_extract_path_text(Content.content_metadata, "difficulty")
                == difficulty
            )

        if tags:
            # Filter by tags in metadata (should contain all specified tags)
            for tag in tags:
                query = query.where(
                    func.json_extract_path(Content.content_metadata, "tags").op("@>")(
                        '["' + tag + '"]'
                    )
                )

        # Build count query (before adding sorting and pagination)
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = Content.created_at  # default
        if sort_by == "updated_at":
            sort_column = Content.updated_at
        elif sort_by == "view_count":
            sort_column = Content.view_count
        elif sort_by == "like_count":
            sort_column = Content.like_count
        elif sort_by == "trending_score":
            sort_column = Content.trending_score
        elif sort_by == "created_at":
            sort_column = Content.created_at

        if order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Execute query
        result = await self.db.execute(query)
        content_items = result.scalars().all()

        # Build response items
        items = []
        for content in content_items:
            # Extract metadata
            metadata = content.content_metadata or {}
            tags_list = metadata.get("tags", [])
            content_difficulty = metadata.get("difficulty")
            duration_minutes = metadata.get("duration_minutes")

            # Build content summary
            item = {
                "id": content.id,
                "title": content.title,
                "description": content.description,
                "content_type": content.content_type.value.lower(),
                "image_url": content.image_url,
                "tags": tags_list,
                "difficulty": content_difficulty,
                "duration_minutes": duration_minutes,
                "author_name": content.author.full_name if content.author else None,
                "category_name": content.category.name if content.category else None,
                "view_count": content.view_count or 0,
                "like_count": content.like_count or 0,
                "created_at": content.created_at,
            }

            items.append(item)

        return {"items": items, "total": total}
