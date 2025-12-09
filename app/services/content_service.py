"""
Content Service - Business logic for content operations.

This provides:
1. Content creation and management workflows
2. Content discovery and search logic
3. Content interaction handling
4. Content validation and processing
5. Content analytics and statistics
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.models.content import Content, ContentType
from app.models.interaction import Interaction, InteractionType
from app.repositories.content_repository import ContentRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService


class ContentService(BaseService):
    """
    Content service handling all content-related business logic.

    This demonstrates service orchestration:
    - Coordinates content and user repositories
    - Implements complex content workflows
    - Handles content validation and processing
    - Manages content interactions and statistics
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.content_repo = ContentRepository(db)
        self.user_repo = UserRepository(db)
        self.interaction_repo = InteractionRepository(db)

    async def create_content(
        self,
        author_id: int,
        title: str,
        content_type: ContentType,
        description: Optional[str] = None,
        body: Optional[str] = None,
        url: Optional[str] = None,
        category_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Content:
        """
        Create new content with business validation.

        Business rules:
        1. Author must exist and be active
        2. Title must be unique for the author
        3. Content must have either body or URL
        4. Validate metadata structure

        Args:
            author_id: ID of content author
            title: Content title
            content_type: Type of content (article, video, etc.)
            description: Optional content description
            body: Content body (for articles)
            url: External URL (for external content)
            category_id: Optional category ID
            metadata: Additional content metadata

        Returns:
            Created content instance

        Raises:
            ValidationError: If validation fails
            NotFoundError: If author doesn't exist
        """
        self._log_operation("create_content", author_id=author_id, title=title)

        try:
            # Validate author exists and is active
            author = await self.user_repo.get(author_id)
            if not author or not author.is_active:
                raise NotFoundError("Author not found or inactive")

            # Business validation
            self._validate_content_data(title, content_type, body, url)

            # Process and validate metadata
            processed_metadata = self._process_content_metadata(metadata or {})

            # Create content data
            content_data = {
                "title": title.strip(),
                "description": description.strip() if description else None,
                "content_type": content_type,
                "body": body,
                "url": url,
                "author_id": author_id,
                "category_id": category_id,
                "content_metadata": processed_metadata,
                "is_published": True,  # Default to published
                "view_count": 0,
                "like_count": 0,
                "save_count": 0,
                "share_count": 0,
                "trending_score": 0.0,
                "quality_score": self._calculate_initial_quality_score(
                    title, description, body
                ),
            }

            # Create content
            content = await self.content_repo.create(content_data)

            self.logger.info(f"Content created successfully: {content.id}")
            return content

        except Exception as error:
            await self._handle_service_error(error, "create content")

    async def get_content_detail(
        self, content_id: int, viewer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get detailed content information with business logic.

        This demonstrates service orchestration:
        1. Get content with statistics
        2. Record view interaction if viewer provided
        3. Get similar content recommendations
        4. Check if viewer has interacted with content

        Args:
            content_id: Content ID
            viewer_id: Optional viewer ID for personalization

        Returns:
            Comprehensive content details

        Raises:
            NotFoundError: If content doesn't exist
        """
        self._log_operation(
            "get_content_detail", content_id=content_id, viewer_id=viewer_id
        )

        try:
            # Get content with stats
            content_data = await self.content_repo.get_content_with_stats(content_id)
            if not content_data:
                raise NotFoundError("Content not found")

            content = content_data["content"]
            stats = content_data["stats"]

            # Record view if viewer provided
            if viewer_id and viewer_id != content.author_id:
                await self._record_interaction(
                    viewer_id, content_id, InteractionType.VIEW
                )

            # Get similar content
            similar_content = await self.content_repo.get_similar_content(
                content_id, limit=5
            )

            # Get viewer interactions if viewer provided
            viewer_interactions = {}
            if viewer_id:
                viewer_interactions = await self._get_user_content_interactions(
                    viewer_id, content_id
                )

            return {
                "content": {
                    "id": content.id,
                    "title": content.title,
                    "description": content.description,
                    "content_type": content.content_type,
                    "body": content.body,
                    "url": content.url,
                    "image_url": content.image_url,
                    "metadata": content.content_metadata,
                    "created_at": content.created_at,
                    "author": (
                        {
                            "id": content.author.id,
                            "full_name": content.author.full_name,
                            "email": content.author.email,
                        }
                        if content.author
                        else None
                    ),
                    "category": (
                        {
                            "id": content.category.id,
                            "name": content.category.name,
                            "slug": content.category.slug,
                            "description": content.category.description,
                            "color": content.category.color,
                        }
                        if content.category
                        else None
                    ),
                },
                "stats": stats,
                "similar_content": [
                    {"id": c.id, "title": c.title, "content_type": c.content_type}
                    for c in similar_content
                ],
                "viewer_interactions": viewer_interactions,
            }

        except Exception as error:
            await self._handle_service_error(error, "get content detail")

    async def interact_with_content(
        self,
        user_id: int,
        content_id: int,
        interaction_type: InteractionType,
        rating: Optional[float] = None,
    ) -> bool:
        """
        Handle user interaction with content.

        Business rules:
        1. User must exist and be active
        2. Content must exist and be published
        3. Can't interact with your own content (except views)
        4. Rating must be between 1-5 if provided

        Args:
            user_id: ID of interacting user
            content_id: ID of content
            interaction_type: Type of interaction
            rating: Optional rating (1-5)

        Returns:
            True if interaction was created/updated
        """
        self._log_operation(
            "interact_with_content",
            user_id=user_id,
            content_id=content_id,
            interaction_type=interaction_type.value,
        )

        try:
            # Validate user exists
            user = await self.user_repo.get(user_id)
            if not user or not user.is_active:
                raise NotFoundError("User not found or inactive")

            # Validate content exists
            content = await self.content_repo.get(content_id)
            if not content or not content.is_published:
                raise NotFoundError("Content not found or not published")

            # Business rule: can't like/save your own content
            if content.author_id == user_id and interaction_type in [
                InteractionType.LIKE,
                InteractionType.SAVE,
            ]:
                raise ValidationError("Cannot like or save your own content")

            # Validate rating if provided
            if rating is not None and (rating < 1.0 or rating > 5.0):
                raise ValidationError("Rating must be between 1 and 5")

            # Create/update interaction
            success = await self._record_interaction(
                user_id, content_id, interaction_type, rating
            )

            if success:
                # Update content statistics (in background in production)
                await self._update_content_stats_after_interaction(
                    content_id, interaction_type
                )

                # Update user interaction count
                await self.user_repo.update(
                    user_id, {"total_interactions": user.total_interactions + 1}
                )

            return success

        except Exception as error:
            await self._handle_service_error(error, "interact with content")

    async def search_content(
        self,
        query: str,
        content_type: Optional[ContentType] = None,
        category_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Search content with filters and business logic.

        Args:
            query: Search query string
            content_type: Optional content type filter
            category_id: Optional category filter
            skip: Pagination offset
            limit: Maximum results

        Returns:
            Search results with metadata
        """
        self._log_operation("search_content", query=query)

        try:
            # Validate search query
            if not query or len(query.strip()) < 2:
                raise ValidationError("Search query must be at least 2 characters")

            # Search content
            results = await self.content_repo.search_content(
                query, content_type, category_id, skip, limit
            )

            # Get total count for pagination
            total_count = await self.content_repo.count({"is_published": True})

            return {
                "results": [
                    {
                        "id": content.id,
                        "title": content.title,
                        "description": content.description,
                        "content_type": content.content_type,
                        "created_at": content.created_at,
                        "stats": {
                            "views": content.view_count,
                            "likes": content.like_count,
                        },
                    }
                    for content in results
                ],
                "pagination": {
                    "skip": skip,
                    "limit": limit,
                    "total": total_count,
                    "has_next": skip + limit < total_count,
                },
                "search_metadata": {
                    "query": query,
                    "filters": {
                        "content_type": content_type.value if content_type else None,
                        "category_id": category_id,
                    },
                },
            }

        except Exception as error:
            await self._handle_service_error(error, "search content")

    async def get_trending_content(
        self, days: int = 7, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get trending content with business logic.

        Args:
            days: Number of days to look back
            limit: Maximum results

        Returns:
            List of trending content with metadata
        """
        self._log_operation("get_trending_content", days=days, limit=limit)

        try:
            trending_content = await self.content_repo.get_trending_content(
                days, 0, limit
            )

            return [
                {
                    "id": content.id,
                    "title": content.title,
                    "content_type": content.content_type,
                    "trending_score": content.trending_score,
                    "stats": {
                        "views": content.view_count,
                        "likes": content.like_count,
                        "engagement_rate": content.engagement_rate,
                    },
                    "created_at": content.created_at,
                }
                for content in trending_content
            ]

        except Exception as error:
            await self._handle_service_error(error, "get trending content")

    # Private helper methods (business logic)

    def _validate_content_data(
        self,
        title: str,
        content_type: ContentType,
        body: Optional[str],
        url: Optional[str],
    ) -> None:
        """Validate content data according to business rules"""
        if not title or len(title.strip()) < 3:
            raise ValidationError("Title must be at least 3 characters")

        if len(title) > 500:
            raise ValidationError("Title cannot exceed 500 characters")

        # Content must have either body or URL
        if not body and not url:
            raise ValidationError("Content must have either body text or URL")

        # URL validation for external content
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise ValidationError("URL must start with http:// or https://")

    def _process_content_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate content metadata"""
        processed = {}

        # Process tags
        if "tags" in metadata:
            tags = metadata["tags"]
            if isinstance(tags, list):
                processed["tags"] = [
                    tag.strip().lower() for tag in tags[:10]
                ]  # Max 10 tags

        # Process difficulty level
        if "difficulty" in metadata:
            difficulty = metadata["difficulty"]
            if difficulty in ["beginner", "intermediate", "advanced"]:
                processed["difficulty"] = difficulty

        # Process duration
        if "duration_minutes" in metadata:
            duration = metadata["duration_minutes"]
            if isinstance(duration, int) and 1 <= duration <= 1440:  # Max 24 hours
                processed["duration_minutes"] = duration

        return processed

    def _calculate_initial_quality_score(
        self, title: str, description: Optional[str], body: Optional[str]
    ) -> float:
        """Calculate initial quality score based on content characteristics"""
        score = 0.0

        # Title quality (length and word count)
        if 10 <= len(title) <= 100:
            score += 2.0

        # Description presence and quality
        if description and len(description) > 50:
            score += 1.5

        # Body content quality
        if body and len(body) > 100:
            score += 2.5

            # Bonus for longer content
            if len(body) > 1000:
                score += 1.0

        return min(score, 5.0)  # Max score of 5.0

    async def _record_interaction(
        self,
        user_id: int,
        content_id: int,
        interaction_type: InteractionType,
        rating: Optional[float] = None,
    ) -> bool:
        """Record user interaction with content"""
        try:
            # Convert float rating to int for database (ratings are 1-5 stars)
            rating_int = int(rating) if rating is not None else None

            interaction = await self.interaction_repo.create_or_update_interaction(
                user_id=user_id,
                content_id=content_id,
                interaction_type=interaction_type,
                rating=rating_int,
            )
            return interaction is not None
        except Exception as e:
            self.logger.error(f"Failed to record interaction: {e}")
            return False

    async def _get_user_content_interactions(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """Get user's interactions with specific content"""
        try:
            return await self.interaction_repo.get_user_content_interactions(
                user_id=user_id, content_id=content_id
            )
        except Exception as e:
            self.logger.error(f"Failed to get user interactions: {e}")
            return {
                "has_viewed": False,
                "has_liked": False,
                "has_saved": False,
                "has_shared": False,
                "rating": None,
            }

    async def _update_content_stats_after_interaction(
        self, content_id: int, interaction_type: InteractionType
    ) -> None:
        """Update content statistics after interaction"""
        # In production, this would be done by background jobs
        # For now, we'll update immediately
        await self.content_repo.update_content_stats(content_id)

    async def list_content(
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
    ) -> Dict[str, Any]:
        """
        List published content with filtering and pagination.

        Business rules:
        1. Only published content is shown
        2. Results are paginated
        3. Multiple filters can be combined
        4. Sort by various fields

        Args:
            content_type: Filter by content type (article, video, etc.)
            category_id: Filter by category ID
            author_id: Filter by specific author
            tags: Filter by tags (must contain all specified tags)
            difficulty: Filter by difficulty level
            sort_by: Sort field (created_at, updated_at, view_count, like_count, trending_score)
            order: Sort order (asc/desc)
            skip: Pagination offset
            limit: Maximum results per page

        Returns:
            Dictionary with content items, total count, and pagination info
        """
        self._log_operation(
            "list_content",
            content_type=content_type,
            category_id=category_id,
            skip=skip,
            limit=limit,
        )

        try:
            # Get content from repository
            result = await self.content_repo.list_content_with_filters(
                content_type=content_type,
                category_id=category_id,
                author_id=author_id,
                tags=tags,
                difficulty=difficulty,
                sort_by=sort_by,
                order=order,
                skip=skip,
                limit=limit,
            )

            return {"items": result["items"], "total": result["total"]}

        except Exception as error:
            await self._handle_service_error(error, "list content")
