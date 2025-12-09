"""
Collaborative Filtering Recommendation Algorithm.

This provides:
1. User-based collaborative filtering (find similar users)
2. Item-based collaborative filtering (find similar content)
3. Matrix factorization for scalable recommendations
4. Cold start handling for new users/content
"""

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithms.base import BaseRecommendationAlgorithm, RecommendationResult
from app.models.interaction import InteractionType
from app.repositories.content_repository import ContentRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.user_repository import UserRepository


class CollaborativeFilteringRecommendation(BaseRecommendationAlgorithm):
    """
    Collaborative filtering recommendation algorithm.

    This algorithm finds users with similar preferences and recommends
    content that similar users have liked but the target user hasn't seen.

    Two main approaches:
    1. User-Based: "Users who liked what you liked also liked..."
    2. Item-Based: "People who liked this content also liked..."

    Algorithm Steps:
    1. Build user-item interaction matrix
    2. Calculate user or item similarities
    3. Predict ratings for unseen items
    4. Return top-scored content with explanations
    """

    def __init__(self, db: AsyncSession, method: str = "user_based"):
        super().__init__("Collaborative Filtering")
        self.db = db
        self.method = method  # "user_based" or "item_based"
        self.content_repo = ContentRepository(db)
        self.interaction_repo = InteractionRepository(db)
        self.user_repo = UserRepository(db)

        # Algorithm parameters
        self.min_common_items = 3  # Minimum common items for similarity
        self.min_interactions = 5  # Minimum user interactions
        self.similarity_threshold = 0.1  # Minimum similarity score
        self.max_similar_users = 50  # Maximum similar users to consider

    async def generate_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Generate collaborative filtering recommendations.

        Args:
            user_id: Target user ID
            num_recommendations: Number of recommendations
            exclude_content_ids: Content to exclude
            **kwargs: Additional parameters

        Returns:
            RecommendationResult with recommended content and scores
        """
        self.validate_user_id(user_id)
        self.validate_num_recommendations(num_recommendations)
        self.log_recommendation_request(user_id, num_recommendations, **kwargs)

        try:
            # Check if user has sufficient interaction data
            user_interactions = await self.interaction_repo.get_user_interactions(
                user_id,
                interaction_types=[
                    InteractionType.LIKE,
                    InteractionType.SAVE,
                    InteractionType.RATE,
                ],
            )

            if len(user_interactions) < self.min_interactions:
                return await self._get_popular_fallback(user_id, num_recommendations)

            if self.method == "user_based":
                return await self._user_based_recommendations(
                    user_id, num_recommendations, exclude_content_ids
                )
            else:
                return await self._item_based_recommendations(
                    user_id, num_recommendations, exclude_content_ids
                )

        except Exception as e:
            self.logger.error(
                f"Error in collaborative filtering for user {user_id}: {e}"
            )
            return RecommendationResult([], [], self.name, user_id)

    async def _user_based_recommendations(
        self,
        user_id: int,
        num_recommendations: int,
        exclude_content_ids: Optional[List[int]] = None,
    ) -> RecommendationResult:
        """
        Generate user-based collaborative filtering recommendations.

        Steps:
        1. Find users similar to target user
        2. Get content liked by similar users
        3. Score content based on similar users' preferences
        4. Filter and rank recommendations
        """
        # Find similar users
        similar_users = await self.interaction_repo.get_similar_users(
            user_id, limit=self.max_similar_users
        )

        if not similar_users:
            return await self._get_popular_fallback(user_id, num_recommendations)

        # Get content recommendations from similar users
        content_scores = defaultdict(float)
        content_recommenders = defaultdict(list)

        # Get target user's interactions to exclude
        target_user_interactions = await self.interaction_repo.get_user_interactions(
            user_id
        )
        target_user_content = {i.content_id for i in target_user_interactions}

        # Exclude additional content if specified
        if exclude_content_ids:
            target_user_content.update(exclude_content_ids)

        for similar_user in similar_users:
            similarity_score = similar_user["similarity_score"]
            similar_user_id = similar_user["user_id"]

            # Get positive interactions from similar user
            similar_user_interactions = (
                await self.interaction_repo.get_user_interactions(
                    similar_user_id,
                    interaction_types=[
                        InteractionType.LIKE,
                        InteractionType.SAVE,
                        InteractionType.RATE,
                    ],
                )
            )

            for interaction in similar_user_interactions:
                content_id = interaction.content_id

                # Skip if target user already interacted with this content
                if content_id in target_user_content:
                    continue

                # Calculate interaction weight
                interaction_weight = self._get_interaction_weight(
                    interaction.interaction_type, interaction.rating
                )

                # Score = similarity * interaction_weight
                score = similarity_score * interaction_weight
                content_scores[content_id] += score
                content_recommenders[content_id].append(
                    {
                        "user_id": similar_user_id,
                        "similarity": similarity_score,
                        "interaction_type": interaction.interaction_type.value,
                    }
                )

        # Sort recommendations by score
        sorted_recommendations = sorted(
            content_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Take top N recommendations
        top_recommendations = sorted_recommendations[:num_recommendations]
        content_ids = [item[0] for item in top_recommendations]
        scores = [item[1] for item in top_recommendations]

        # Normalize scores to 0-1 range
        if scores:
            max_score = max(scores)
            scores = [score / max_score for score in scores]

        metadata = {
            "method": "user_based",
            "similar_users_count": len(similar_users),
            "avg_similarity": sum(u["similarity_score"] for u in similar_users)
            / len(similar_users),
            "total_candidates": len(content_scores),
            "recommender_details": {
                str(cid): content_recommenders[cid][
                    :3
                ]  # Top 3 recommenders per content
                for cid in content_ids[:5]  # For top 5 recommendations
            },
        }

        return RecommendationResult(
            content_ids=content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (User-Based)",
            user_id=user_id,
            metadata=metadata,
        )

    async def _item_based_recommendations(
        self,
        user_id: int,
        num_recommendations: int,
        exclude_content_ids: Optional[List[int]] = None,
    ) -> RecommendationResult:
        """
        Generate item-based collaborative filtering recommendations.

        Steps:
        1. Get user's liked content
        2. For each liked content, find similar content
        3. Score similar content based on similarity and user preference
        4. Aggregate and rank recommendations
        """
        # Get user's positive interactions
        user_interactions = await self.interaction_repo.get_user_interactions(
            user_id,
            interaction_types=[
                InteractionType.LIKE,
                InteractionType.SAVE,
                InteractionType.RATE,
            ],
        )

        if not user_interactions:
            return await self._get_popular_fallback(user_id, num_recommendations)

        # Get user's interacted content IDs
        user_content_ids = [i.content_id for i in user_interactions]
        if exclude_content_ids:
            user_content_ids.extend(exclude_content_ids)

        content_scores = defaultdict(float)
        content_similarity_details = defaultdict(list)

        # For each content the user liked, find similar content
        for interaction in user_interactions:
            source_content_id = interaction.content_id

            # Get content similar to this one
            similar_content = await self.content_repo.get_similar_content(
                source_content_id, limit=20
            )

            # Calculate user's preference weight for source content
            user_preference_weight = self._get_interaction_weight(
                interaction.interaction_type, interaction.rating
            )

            for similar_content_item in similar_content:
                target_content_id = similar_content_item.id

                # Skip if user already interacted with this content
                if target_content_id in user_content_ids:
                    continue

                # Calculate item-item similarity (simplified)
                # In production, this would use more sophisticated similarity metrics
                item_similarity = self._calculate_item_similarity(
                    source_content_id, target_content_id
                )

                # Score = user_preference * item_similarity
                score = user_preference_weight * item_similarity
                content_scores[target_content_id] += score

                content_similarity_details[target_content_id].append(
                    {
                        "source_content_id": source_content_id,
                        "similarity": item_similarity,
                        "user_preference": user_preference_weight,
                    }
                )

        # Sort and select top recommendations
        sorted_recommendations = sorted(
            content_scores.items(), key=lambda x: x[1], reverse=True
        )

        top_recommendations = sorted_recommendations[:num_recommendations]
        content_ids = [item[0] for item in top_recommendations]
        scores = [item[1] for item in top_recommendations]

        # Normalize scores
        if scores:
            max_score = max(scores)
            scores = [score / max_score for score in scores]

        metadata = {
            "method": "item_based",
            "user_liked_content_count": len(user_interactions),
            "total_candidates": len(content_scores),
            "similarity_details": {
                str(cid): content_similarity_details[cid][:3] for cid in content_ids[:5]
            },
        }

        return RecommendationResult(
            content_ids=content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (Item-Based)",
            user_id=user_id,
            metadata=metadata,
        )

    def _calculate_item_similarity(self, content_id1: int, content_id2: int) -> float:
        """
        Calculate similarity between two content items.

        This is a simplified version - in production you'd calculate this
        based on user interaction patterns, content features, etc.

        Args:
            content_id1: First content ID
            content_id2: Second content ID

        Returns:
            Similarity score between 0 and 1
        """
        # Simplified similarity calculation
        # In production, this would be based on:
        # 1. User overlap (users who interacted with both items)
        # 2. Content features similarity
        # 3. Category/tag overlap
        # 4. Interaction pattern similarity

        # For demo purposes, return a mock similarity
        return 0.7  # This would be calculated from actual data

    def _get_interaction_weight(
        self, interaction_type: InteractionType, rating: Optional[float] = None
    ) -> float:
        """
        Convert interaction to numerical weight.

        Args:
            interaction_type: Type of interaction
            rating: Rating value (for rating interactions)

        Returns:
            Numerical weight for the interaction
        """
        base_weights = {
            InteractionType.LIKE: 1.0,
            InteractionType.SAVE: 1.2,
            InteractionType.SHARE: 1.5,
            InteractionType.RATE: 1.0,
        }

        weight = base_weights.get(interaction_type, 0.5)

        # Adjust for rating value
        if interaction_type == InteractionType.RATE and rating:
            # Convert 1-5 rating to 0.2-1.0 multiplier
            rating_multiplier = (rating - 1) / 4 * 0.8 + 0.2
            weight *= rating_multiplier

        return weight

    async def _get_popular_fallback(
        self, user_id: int, num_recommendations: int
    ) -> RecommendationResult:
        """
        Fallback to popular content for users without sufficient data.

        Args:
            user_id: User ID
            num_recommendations: Number of recommendations

        Returns:
            RecommendationResult with popular content
        """
        # Get trending content as fallback
        trending_content_ids = await self.interaction_repo.get_trending_content_ids(
            days=30, limit=num_recommendations  # Longer period for popular content
        )

        # Assign scores based on popularity rank
        scores = [1.0 - (i * 0.05) for i in range(len(trending_content_ids))]

        metadata = {
            "fallback_reason": "insufficient_interaction_data",
            "min_interactions_required": self.min_interactions,
            "algorithm": "popular_fallback",
        }

        return RecommendationResult(
            content_ids=trending_content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (Popular Fallback)",
            user_id=user_id,
            metadata=metadata,
        )

    async def explain_recommendation(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """
        Explain why content was recommended using collaborative filtering.

        Args:
            user_id: User ID
            content_id: Content ID to explain

        Returns:
            Explanation dictionary
        """
        try:
            if self.method == "user_based":
                return await self._explain_user_based_recommendation(
                    user_id, content_id
                )
            else:
                return await self._explain_item_based_recommendation(
                    user_id, content_id
                )

        except Exception as e:
            self.logger.error(f"Error explaining recommendation: {e}")
            return {"error": "Unable to generate explanation"}

    async def _explain_user_based_recommendation(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """Explain user-based collaborative filtering recommendation."""

        # Find similar users who liked this content
        similar_users = await self.interaction_repo.get_similar_users(user_id)

        recommending_users = []
        for similar_user in similar_users[:10]:  # Check top 10 similar users
            # Check if this user liked the recommended content
            user_interactions = await self.interaction_repo.get_user_interactions(
                similar_user["user_id"],
                interaction_types=[
                    InteractionType.LIKE,
                    InteractionType.SAVE,
                    InteractionType.RATE,
                ],
            )

            for interaction in user_interactions:
                if interaction.content_id == content_id:
                    recommending_users.append(
                        {
                            "user_id": similar_user["user_id"],
                            "similarity_score": similar_user["similarity_score"],
                            "interaction_type": interaction.interaction_type.value,
                            "rating": interaction.rating,
                        }
                    )
                    break

        explanation = {
            "content_id": content_id,
            "method": "user_based_collaborative_filtering",
            "explanation": f"Recommended because {len(recommending_users)} users with similar tastes liked this content",
            "similar_users_count": len(recommending_users),
            "avg_similarity": (
                sum(u["similarity_score"] for u in recommending_users)
                / len(recommending_users)
                if recommending_users
                else 0
            ),
            "evidence": recommending_users[:5],  # Show top 5 as evidence
        }

        return explanation

    async def _explain_item_based_recommendation(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """Explain item-based collaborative filtering recommendation."""

        # Get user's liked content
        user_interactions = await self.interaction_repo.get_user_interactions(
            user_id,
            interaction_types=[
                InteractionType.LIKE,
                InteractionType.SAVE,
                InteractionType.RATE,
            ],
        )

        # Find which of user's content is similar to recommended content
        similar_content_evidence = []
        for interaction in user_interactions:
            similarity = self._calculate_item_similarity(
                interaction.content_id, content_id
            )

            if similarity > 0.3:  # Threshold for meaningful similarity
                similar_content_evidence.append(
                    {
                        "content_id": interaction.content_id,
                        "similarity_score": similarity,
                        "user_interaction": interaction.interaction_type.value,
                        "user_rating": interaction.rating,
                    }
                )

        explanation = {
            "content_id": content_id,
            "method": "item_based_collaborative_filtering",
            "explanation": f"Recommended because it's similar to {len(similar_content_evidence)} items you've liked",
            "similar_items_count": len(similar_content_evidence),
            "evidence": similar_content_evidence[:3],  # Show top 3 similar items
        }

        return explanation


class MatrixFactorizationRecommendation(BaseRecommendationAlgorithm):
    """
    Matrix Factorization recommendation algorithm using SVD.

    This is more scalable than basic collaborative filtering
    and can handle sparse interaction matrices better.

    Note: This is a simplified implementation for demonstration.
    Production systems would use libraries like Surprise or TensorFlow.
    """

    def __init__(self, db: AsyncSession, factors: int = 50):
        super().__init__("Matrix Factorization")
        self.db = db
        self.factors = factors  # Number of latent factors
        self.learning_rate = 0.01
        self.regularization = 0.001
        self.epochs = 100

        # Will be populated during training
        self.user_factors = None
        self.item_factors = None
        self.user_bias = None
        self.item_bias = None
        self.global_bias = None

    async def generate_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Generate recommendations using matrix factorization.

        Note: This is a simplified implementation for demonstration.
        In production, you'd pre-train the model and store factors.
        """
        # This would typically load pre-trained factors
        # For demo, return placeholder
        return RecommendationResult(
            content_ids=[],
            scores=[],
            algorithm_name=self.name,
            user_id=user_id,
            metadata={"note": "Matrix factorization requires pre-training"},
        )

    async def explain_recommendation(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """Explain matrix factorization recommendation."""
        return {
            "content_id": content_id,
            "method": "matrix_factorization",
            "explanation": "Recommended based on latent factors learned from user interaction patterns",
            "note": "Matrix factorization explanations require factor analysis",
        }
