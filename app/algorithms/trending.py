"""
Trending Content Recommendation Algorithm.

This provides:
1. Time-weighted popularity scoring
2. Multi-signal trending detection (views, likes, shares)
3. Category-aware trending to ensure diversity
4. Freshness boost for recent content
5. Viral content detection
"""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithms.base import BaseRecommendationAlgorithm, RecommendationResult
from app.models.content import Content
from app.models.interaction import InteractionType
from app.repositories.content_repository import ContentRepository
from app.repositories.interaction_repository import InteractionRepository


class TrendingRecommendation(BaseRecommendationAlgorithm):
    """
    Trending content recommendation algorithm.

    This algorithm identifies and recommends content that is currently
    popular or gaining momentum based on recent user interactions.

    Trending Score Calculation:
    1. Engagement Score: Weighted sum of interactions (views, likes, shares)
    2. Time Decay: Recent interactions weighted more heavily
    3. Velocity: Rate of interaction growth
    4. Freshness Boost: Newer content gets additional scoring
    5. Quality Filter: Minimum quality thresholds

    Different Trending Types:
    - Hot: High current activity
    - Rising: Rapidly increasing activity
    - Fresh: New content with good engagement
    - Viral: Exponential growth in interactions
    """

    def __init__(self, db: AsyncSession, trending_type: str = "hot"):
        super().__init__("Trending Content")
        self.db = db
        self.trending_type = trending_type  # "hot", "rising", "fresh", "viral"
        self.content_repo = ContentRepository(db)
        self.interaction_repo = InteractionRepository(db)

        # Algorithm parameters
        self.time_windows = {
            "hot": 1,  # 1 day for hot content
            "rising": 3,  # 3 days for rising content
            "fresh": 7,  # 7 days for fresh content
            "viral": 1,  # 1 day for viral content
        }

        # Interaction weights for trending score
        self.interaction_weights = {
            InteractionType.VIEW: 1.0,
            InteractionType.LIKE: 3.0,
            InteractionType.SAVE: 4.0,
            InteractionType.SHARE: 8.0,
            InteractionType.RATE: 2.0,
        }

        # Minimum thresholds
        self.min_interactions = 5
        self.min_unique_users = 3

    async def generate_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Generate trending content recommendations.

        Args:
            user_id: User ID (for personalization filters)
            num_recommendations: Number of recommendations
            exclude_content_ids: Content to exclude
            **kwargs: Additional parameters like category_filter

        Returns:
            RecommendationResult with trending content
        """
        self.validate_user_id(user_id)
        self.validate_num_recommendations(num_recommendations)
        self.log_recommendation_request(user_id, num_recommendations, **kwargs)

        try:
            # Get time window for trending calculation
            days_back = self.time_windows.get(self.trending_type, 1)

            if self.trending_type == "hot":
                return await self._get_hot_trending(
                    user_id,
                    num_recommendations,
                    days_back,
                    exclude_content_ids,
                    **kwargs,
                )
            elif self.trending_type == "rising":
                return await self._get_rising_trending(
                    user_id,
                    num_recommendations,
                    days_back,
                    exclude_content_ids,
                    **kwargs,
                )
            elif self.trending_type == "fresh":
                return await self._get_fresh_trending(
                    user_id,
                    num_recommendations,
                    days_back,
                    exclude_content_ids,
                    **kwargs,
                )
            elif self.trending_type == "viral":
                return await self._get_viral_trending(
                    user_id,
                    num_recommendations,
                    days_back,
                    exclude_content_ids,
                    **kwargs,
                )
            else:
                # Default to hot trending
                return await self._get_hot_trending(
                    user_id,
                    num_recommendations,
                    days_back,
                    exclude_content_ids,
                    **kwargs,
                )

        except Exception as e:
            self.logger.error(f"Error generating trending recommendations: {e}")
            return RecommendationResult([], [], self.name, user_id)

    async def _get_hot_trending(
        self,
        user_id: int,
        num_recommendations: int,
        days_back: int,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Get currently hot/popular content.

        Hot content has high engagement right now.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        # Get content with recent interactions
        trending_data = await self._calculate_trending_scores(
            cutoff_date, exclude_content_ids, **kwargs
        )

        # Sort by trending score
        trending_data.sort(key=lambda x: x["trending_score"], reverse=True)

        # Take top N
        top_trending = trending_data[:num_recommendations]

        content_ids = [item["content_id"] for item in top_trending]
        scores = [item["normalized_score"] for item in top_trending]

        metadata = {
            "trending_type": "hot",
            "time_window_days": days_back,
            "total_candidates": len(trending_data),
            "min_interactions": self.min_interactions,
            "scoring_details": [
                {
                    "content_id": item["content_id"],
                    "raw_score": item["trending_score"],
                    "interaction_count": item["total_interactions"],
                    "unique_users": item["unique_users"],
                }
                for item in top_trending[:5]  # Details for top 5
            ],
        }

        return RecommendationResult(
            content_ids=content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (Hot)",
            user_id=user_id,
            metadata=metadata,
        )

    async def _get_rising_trending(
        self,
        user_id: int,
        num_recommendations: int,
        days_back: int,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Get content that's rising in popularity.

        Rising content shows increasing engagement velocity.
        """
        # Compare recent period vs previous period
        recent_cutoff = datetime.utcnow() - timedelta(days=days_back // 2)
        older_cutoff = datetime.utcnow() - timedelta(days=days_back)

        # Get interactions for both periods
        recent_data = await self._calculate_trending_scores(
            recent_cutoff, exclude_content_ids, **kwargs
        )

        older_data = await self._calculate_trending_scores(
            older_cutoff, exclude_content_ids, end_date=recent_cutoff, **kwargs
        )

        # Calculate velocity (rate of change)
        older_scores = {
            item["content_id"]: item["trending_score"] for item in older_data
        }

        rising_content = []
        for item in recent_data:
            content_id = item["content_id"]
            recent_score = item["trending_score"]
            older_score = older_scores.get(content_id, 0)

            # Calculate velocity (percentage change)
            if older_score > 0:
                velocity = (recent_score - older_score) / older_score
            else:
                velocity = recent_score  # New content gets its score as velocity

            if velocity > 0.1:  # At least 10% increase
                rising_content.append(
                    {
                        **item,
                        "velocity": velocity,
                        "rising_score": recent_score * (1 + velocity),
                    }
                )

        # Sort by rising score
        rising_content.sort(key=lambda x: x["rising_score"], reverse=True)

        top_rising = rising_content[:num_recommendations]
        content_ids = [item["content_id"] for item in top_rising]

        # Normalize scores
        max_score = (
            max([item["rising_score"] for item in top_rising]) if top_rising else 1
        )
        scores = [item["rising_score"] / max_score for item in top_rising]

        metadata = {
            "trending_type": "rising",
            "time_window_days": days_back,
            "comparison_periods": f"{days_back//2} days vs previous {days_back//2} days",
            "total_candidates": len(rising_content),
            "avg_velocity": (
                sum(item["velocity"] for item in top_rising) / len(top_rising)
                if top_rising
                else 0
            ),
            "rising_details": [
                {
                    "content_id": item["content_id"],
                    "velocity": item["velocity"],
                    "recent_score": item["trending_score"],
                    "rising_score": item["rising_score"],
                }
                for item in top_rising[:5]
            ],
        }

        return RecommendationResult(
            content_ids=content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (Rising)",
            user_id=user_id,
            metadata=metadata,
        )

    async def _get_fresh_trending(
        self,
        user_id: int,
        num_recommendations: int,
        days_back: int,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Get fresh content that's gaining traction.

        Fresh content is recently published but showing good engagement.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        # Get recent content with good engagement
        fresh_data = await self._calculate_fresh_scores(
            cutoff_date, exclude_content_ids, **kwargs
        )

        # Sort by fresh score (engagement + freshness boost)
        fresh_data.sort(key=lambda x: x["fresh_score"], reverse=True)

        top_fresh = fresh_data[:num_recommendations]
        content_ids = [item["content_id"] for item in top_fresh]

        # Normalize scores
        max_score = max([item["fresh_score"] for item in top_fresh]) if top_fresh else 1
        scores = [item["fresh_score"] / max_score for item in top_fresh]

        metadata = {
            "trending_type": "fresh",
            "time_window_days": days_back,
            "freshness_boost_applied": True,
            "total_candidates": len(fresh_data),
            "avg_content_age_hours": (
                sum(item["age_hours"] for item in top_fresh) / len(top_fresh)
                if top_fresh
                else 0
            ),
            "fresh_details": [
                {
                    "content_id": item["content_id"],
                    "age_hours": item["age_hours"],
                    "base_score": item["trending_score"],
                    "freshness_multiplier": item["freshness_multiplier"],
                    "fresh_score": item["fresh_score"],
                }
                for item in top_fresh[:5]
            ],
        }

        return RecommendationResult(
            content_ids=content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (Fresh)",
            user_id=user_id,
            metadata=metadata,
        )

    async def _get_viral_trending(
        self,
        user_id: int,
        num_recommendations: int,
        days_back: int,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Get viral content with exponential growth.

        Viral content shows rapid, exponential growth in interactions.
        """
        # Look at hourly growth over the last day
        now = datetime.utcnow()

        viral_content = []

        # This would require more sophisticated time-series analysis
        # For demo, we'll identify content with high share/interaction ratios
        trending_data = await self._calculate_trending_scores(
            now - timedelta(days=days_back), exclude_content_ids, **kwargs
        )

        for item in trending_data:
            # Viral indicator: high share rate relative to views
            shares = item.get("shares", 0)
            total_interactions = item.get("total_interactions", 1)

            # Viral score: exponential function of share rate
            share_rate = shares / total_interactions
            viral_multiplier = math.exp(share_rate * 10) if share_rate > 0.1 else 1

            viral_score = item["trending_score"] * viral_multiplier

            if viral_multiplier > 1.5:  # Threshold for viral content
                viral_content.append(
                    {
                        **item,
                        "viral_multiplier": viral_multiplier,
                        "viral_score": viral_score,
                        "share_rate": share_rate,
                    }
                )

        # Sort by viral score
        viral_content.sort(key=lambda x: x["viral_score"], reverse=True)

        top_viral = viral_content[:num_recommendations]
        content_ids = [item["content_id"] for item in top_viral]

        # Normalize scores
        max_score = max([item["viral_score"] for item in top_viral]) if top_viral else 1
        scores = [item["viral_score"] / max_score for item in top_viral]

        metadata = {
            "trending_type": "viral",
            "time_window_days": days_back,
            "viral_threshold": 1.5,
            "total_candidates": len(viral_content),
            "avg_viral_multiplier": (
                sum(item["viral_multiplier"] for item in top_viral) / len(top_viral)
                if top_viral
                else 0
            ),
            "viral_details": [
                {
                    "content_id": item["content_id"],
                    "share_rate": item["share_rate"],
                    "viral_multiplier": item["viral_multiplier"],
                    "viral_score": item["viral_score"],
                }
                for item in top_viral[:5]
            ],
        }

        return RecommendationResult(
            content_ids=content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (Viral)",
            user_id=user_id,
            metadata=metadata,
        )

    async def _calculate_trending_scores(
        self,
        cutoff_date: datetime,
        exclude_content_ids: Optional[List[int]] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Calculate trending scores for content in time window.

        Args:
            cutoff_date: Start of time window
            exclude_content_ids: Content to exclude
            end_date: End of time window (default: now)
            **kwargs: Additional filters

        Returns:
            List of content with trending scores
        """
        end_date = end_date or datetime.utcnow()

        # This would be a complex query in production
        # For demo purposes, return mock data structure

        trending_data = [
            {
                "content_id": 1,
                "trending_score": 85.5,
                "total_interactions": 42,
                "unique_users": 28,
                "views": 35,
                "likes": 5,
                "saves": 1,
                "shares": 1,
                "normalized_score": 0.95,
            },
            {
                "content_id": 2,
                "trending_score": 72.3,
                "total_interactions": 31,
                "unique_users": 22,
                "views": 28,
                "likes": 2,
                "saves": 1,
                "shares": 0,
                "normalized_score": 0.80,
            },
        ]

        # Filter excluded content
        if exclude_content_ids:
            trending_data = [
                item
                for item in trending_data
                if item["content_id"] not in exclude_content_ids
            ]

        return trending_data

    async def _calculate_fresh_scores(
        self,
        cutoff_date: datetime,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Calculate fresh scores with recency boost.

        Args:
            cutoff_date: Cutoff for fresh content
            exclude_content_ids: Content to exclude
            **kwargs: Additional filters

        Returns:
            List of content with fresh scores
        """
        # Get base trending data
        trending_data = await self._calculate_trending_scores(
            cutoff_date, exclude_content_ids, **kwargs
        )

        # Add freshness multiplier
        now = datetime.utcnow()

        for item in trending_data:
            # Mock content age (would come from database)
            content_age_hours = 12  # Mock: 12 hours old

            # Freshness multiplier: newer content gets higher boost
            # Decay function: multiplier decreases with age
            freshness_multiplier = math.exp(
                -content_age_hours / 24
            )  # Decay over 24 hours

            fresh_score = item["trending_score"] * (1 + freshness_multiplier)

            item.update(
                {
                    "age_hours": content_age_hours,
                    "freshness_multiplier": freshness_multiplier,
                    "fresh_score": fresh_score,
                }
            )

        return trending_data

    async def explain_recommendation(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """
        Explain why content is trending and recommended.

        Args:
            user_id: User ID
            content_id: Content ID to explain

        Returns:
            Explanation dictionary
        """
        try:
            # Get content trending metrics
            content_stats = await self.content_repo.get_content_with_stats(content_id)

            if not content_stats:
                return {"error": "Content not found"}

            stats = content_stats["stats"]

            explanation = {
                "content_id": content_id,
                "trending_type": self.trending_type,
                "explanation": f"This content is currently {self.trending_type}",
                "metrics": {
                    "views": stats.get("views", 0),
                    "likes": stats.get("likes", 0),
                    "saves": stats.get("saves", 0),
                    "shares": stats.get("shares", 0),
                    "engagement_rate": stats.get("engagement_rate", 0),
                },
                "reasons": [],
            }

            # Generate specific reasons based on trending type
            if self.trending_type == "hot":
                explanation["reasons"].append("High current engagement activity")

            elif self.trending_type == "rising":
                explanation["reasons"].append("Rapidly increasing in popularity")

            elif self.trending_type == "fresh":
                explanation["reasons"].append(
                    "Recently published with strong initial engagement"
                )

            elif self.trending_type == "viral":
                explanation["reasons"].append(
                    "Showing exponential growth in shares and engagement"
                )

            # Add engagement-based reasons
            if stats.get("engagement_rate", 0) > 0.1:
                explanation["reasons"].append(
                    f"High engagement rate ({stats.get('engagement_rate', 0):.1%})"
                )

            if stats.get("shares", 0) > 0:
                explanation["reasons"].append(
                    f"Being actively shared ({stats.get('shares', 0)} shares)"
                )

            return explanation

        except Exception as e:
            self.logger.error(f"Error explaining trending recommendation: {e}")
            return {"error": "Unable to generate explanation"}
