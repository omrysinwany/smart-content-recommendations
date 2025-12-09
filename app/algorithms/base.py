"""
Base recommendation algorithm interface.

This provides:
1. Abstract base class for all recommendation algorithms
2. Common functionality and patterns
3. Algorithm evaluation metrics
4. Caching and performance utilities
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RecommendationResult:
    """
    Container for recommendation algorithm results.

    This standardizes the output format across all algorithms
    and provides metadata for evaluation and debugging.
    """

    def __init__(
        self,
        content_ids: List[int],
        scores: List[float],
        algorithm_name: str,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize recommendation result.

        Args:
            content_ids: List of recommended content IDs
            scores: Confidence/relevance scores for each recommendation
            algorithm_name: Name of algorithm that generated recommendations
            user_id: User ID recommendations are for
            metadata: Additional algorithm-specific information
        """
        self.content_ids = content_ids
        self.scores = scores
        self.algorithm_name = algorithm_name
        self.user_id = user_id
        self.metadata = metadata or {}
        self.generated_at = datetime.utcnow()

        # Validate inputs
        if len(content_ids) != len(scores):
            raise ValueError("content_ids and scores must have same length")

    def get_top_n(self, n: int) -> Tuple[List[int], List[float]]:
        """Get top N recommendations."""
        if n >= len(self.content_ids):
            return self.content_ids, self.scores

        # Sort by score descending and take top N
        sorted_pairs = sorted(
            zip(self.content_ids, self.scores), key=lambda x: x[1], reverse=True
        )

        top_content_ids = [pair[0] for pair in sorted_pairs[:n]]
        top_scores = [pair[1] for pair in sorted_pairs[:n]]

        return top_content_ids, top_scores

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content_ids": self.content_ids,
            "scores": self.scores,
            "algorithm_name": self.algorithm_name,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
        }


class BaseRecommendationAlgorithm(ABC):
    """
    Abstract base class for recommendation algorithms.

    This defines the interface that all recommendation algorithms
    must implement, ensuring consistency and interoperability.
    """

    def __init__(self, name: str):
        """
        Initialize the algorithm.

        Args:
            name: Human-readable name for this algorithm
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def generate_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs,
    ) -> RecommendationResult:
        """
        Generate content recommendations for a user.

        Args:
            user_id: User ID to generate recommendations for
            num_recommendations: Number of recommendations to generate
            exclude_content_ids: Content IDs to exclude from recommendations
            **kwargs: Algorithm-specific parameters

        Returns:
            RecommendationResult with content IDs and scores

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def explain_recommendation(
        self, user_id: int, content_id: int
    ) -> Dict[str, Any]:
        """
        Explain why content was recommended to user.

        Args:
            user_id: User ID
            content_id: Content ID to explain

        Returns:
            Dictionary with explanation details

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        pass

    def get_algorithm_info(self) -> Dict[str, Any]:
        """
        Get information about this algorithm.

        Returns:
            Dictionary with algorithm metadata
        """
        return {
            "name": self.name,
            "class": self.__class__.__name__,
            "description": self.__doc__.strip() if self.__doc__ else "No description",
            "version": "1.0.0",
        }

    def validate_user_id(self, user_id: int) -> None:
        """
        Validate user ID parameter.

        Args:
            user_id: User ID to validate

        Raises:
            ValueError: If user_id is invalid
        """
        if not isinstance(user_id, int) or user_id < 0:
            raise ValueError("user_id must be a non-negative integer")

    def validate_num_recommendations(self, num_recommendations: int) -> None:
        """
        Validate num_recommendations parameter.

        Args:
            num_recommendations: Number of recommendations to validate

        Raises:
            ValueError: If num_recommendations is invalid
        """
        if not isinstance(num_recommendations, int) or num_recommendations <= 0:
            raise ValueError("num_recommendations must be a positive integer")

        if num_recommendations > 100:
            raise ValueError("num_recommendations cannot exceed 100")

    def log_recommendation_request(
        self, user_id: int, num_recommendations: int, **kwargs
    ) -> None:
        """
        Log recommendation request for debugging and analytics.

        Args:
            user_id: User ID
            num_recommendations: Number of recommendations requested
            **kwargs: Additional parameters
        """
        self.logger.info(
            f"Generating {num_recommendations} recommendations for user {user_id} "
            f"using {self.name} algorithm"
        )

        if kwargs:
            self.logger.debug(f"Additional parameters: {kwargs}")

    def calculate_diversity_score(
        self, content_ids: List[int], content_data: List[Dict]
    ) -> float:
        """
        Calculate diversity score for a list of recommendations.

        Diversity measures how different the recommended content is
        from each other (avoiding echo chambers).

        Args:
            content_ids: List of content IDs
            content_data: List of content metadata

        Returns:
            Diversity score between 0 and 1 (higher = more diverse)
        """
        if len(content_ids) < 2:
            return 1.0  # Single item is perfectly diverse

        # Calculate diversity based on categories and content types
        categories = set()
        content_types = set()

        for content in content_data:
            if content.get("category_id"):
                categories.add(content["category_id"])
            if content.get("content_type"):
                content_types.add(content["content_type"])

        # Diversity score based on unique categories and types
        category_diversity = len(categories) / len(content_ids)
        type_diversity = len(content_types) / len(content_ids)

        # Weight categories more heavily than types
        diversity_score = (category_diversity * 0.7) + (type_diversity * 0.3)

        return min(diversity_score, 1.0)

    def apply_business_rules(
        self, recommendations: List[Tuple[int, float]], user_profile: Dict[str, Any]
    ) -> List[Tuple[int, float]]:
        """
        Apply business rules to recommendations.

        This allows for business logic like:
        - Promoting featured content
        - Respecting user preferences
        - Content freshness requirements

        Args:
            recommendations: List of (content_id, score) tuples
            user_profile: User profile information

        Returns:
            Modified list of recommendations
        """
        # Example business rules (can be overridden by subclasses)

        # Rule 1: Boost score for content matching user's preferred difficulty
        preferred_difficulty = user_profile.get("preferences", {}).get("difficulty")
        if preferred_difficulty:
            # This would require content metadata - simplified for example
            pass

        # Rule 2: Ensure minimum content freshness
        # Filter out content older than user's freshness preference
        max_age_days = user_profile.get("preferences", {}).get(
            "max_content_age_days", 365
        )
        # This would require content creation dates - simplified for example

        return recommendations

    def combine_scores(
        self, scores_list: List[List[float]], weights: List[float]
    ) -> List[float]:
        """
        Combine multiple score lists with weighted averaging.

        Used by hybrid algorithms to combine different scoring methods.

        Args:
            scores_list: List of score lists to combine
            weights: Weights for each score list (must sum to 1.0)

        Returns:
            Combined scores

        Raises:
            ValueError: If weights don't sum to 1.0 or lists have different lengths
        """
        if abs(sum(weights) - 1.0) > 0.001:
            raise ValueError("Weights must sum to 1.0")

        if not scores_list:
            return []

        # Validate all score lists have same length
        first_length = len(scores_list[0])
        for scores in scores_list:
            if len(scores) != first_length:
                raise ValueError("All score lists must have same length")

        # Combine scores with weighted average
        combined_scores = []
        for i in range(first_length):
            weighted_sum = sum(
                scores[i] * weight for scores, weight in zip(scores_list, weights)
            )
            combined_scores.append(weighted_sum)

        return combined_scores


class AlgorithmEvaluator:
    """
    Utility class for evaluating recommendation algorithm performance.

    This provides metrics commonly used in recommender systems:
    - Precision@K: Relevance of top K recommendations
    - Recall@K: Coverage of relevant items in top K
    - Diversity: How different recommendations are from each other
    - Novelty: How new/unexpected recommendations are
    """

    @staticmethod
    def calculate_precision_at_k(
        recommended_ids: List[int], relevant_ids: List[int], k: int
    ) -> float:
        """
        Calculate Precision@K metric.

        Precision@K = (Number of relevant items in top K) / K

        Args:
            recommended_ids: List of recommended content IDs (ordered by relevance)
            relevant_ids: List of actually relevant content IDs
            k: Number of top recommendations to consider

        Returns:
            Precision@K score between 0 and 1
        """
        if k <= 0 or len(recommended_ids) == 0:
            return 0.0

        top_k = recommended_ids[:k]
        relevant_in_top_k = len([id for id in top_k if id in relevant_ids])

        return relevant_in_top_k / k

    @staticmethod
    def calculate_recall_at_k(
        recommended_ids: List[int], relevant_ids: List[int], k: int
    ) -> float:
        """
        Calculate Recall@K metric.

        Recall@K = (Number of relevant items in top K) / (Total relevant items)

        Args:
            recommended_ids: List of recommended content IDs
            relevant_ids: List of actually relevant content IDs
            k: Number of top recommendations to consider

        Returns:
            Recall@K score between 0 and 1
        """
        if len(relevant_ids) == 0:
            return 0.0

        top_k = recommended_ids[:k]
        relevant_in_top_k = len([id for id in top_k if id in relevant_ids])

        return relevant_in_top_k / len(relevant_ids)

    @staticmethod
    def calculate_ndcg_at_k(
        recommended_ids: List[int], relevance_scores: Dict[int, float], k: int
    ) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain@K.

        NDCG considers both relevance and ranking position.

        Args:
            recommended_ids: List of recommended content IDs
            relevance_scores: Dictionary mapping content_id to relevance score
            k: Number of top recommendations to consider

        Returns:
            NDCG@K score between 0 and 1
        """
        import math

        if k <= 0:
            return 0.0

        # Calculate DCG (Discounted Cumulative Gain)
        dcg = 0.0
        for i, content_id in enumerate(recommended_ids[:k]):
            relevance = relevance_scores.get(content_id, 0.0)
            if i == 0:
                dcg += relevance
            else:
                dcg += relevance / math.log2(i + 1)

        # Calculate IDCG (Ideal DCG) - best possible ranking
        sorted_relevance = sorted(relevance_scores.values(), reverse=True)[:k]
        idcg = 0.0
        for i, relevance in enumerate(sorted_relevance):
            if i == 0:
                idcg += relevance
            else:
                idcg += relevance / math.log2(i + 1)

        # Return normalized score
        return dcg / idcg if idcg > 0 else 0.0
