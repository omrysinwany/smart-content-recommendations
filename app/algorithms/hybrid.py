"""
Hybrid Recommendation Algorithm.

This provides:
1. Intelligent combination of multiple recommendation approaches
2. Dynamic weight adjustment based on user profile and context
3. Diversity optimization to avoid filter bubbles
4. Fallback strategies for different scenarios
5. A/B testing framework for algorithm optimization
"""

import random
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithms.base import BaseRecommendationAlgorithm, RecommendationResult
from app.algorithms.content_based import ContentBasedRecommendation
from app.algorithms.collaborative_filtering import CollaborativeFilteringRecommendation
from app.algorithms.trending import TrendingRecommendation
from app.repositories.user_repository import UserRepository
from app.repositories.interaction_repository import InteractionRepository


class HybridRecommendation(BaseRecommendationAlgorithm):
    """
    Hybrid recommendation algorithm that combines multiple approaches.
    
    Strategy:
    1. Content-Based: Recommends based on user's content preferences
    2. Collaborative Filtering: Recommends based on similar users
    3. Trending: Recommends popular/viral content
    4. Diversity: Ensures recommendations aren't too similar
    
    The algorithm dynamically adjusts weights based on:
    - User interaction history (more data = more personalization)
    - Content availability (cold start problems)
    - Context (time of day, device, etc.)
    - User feedback and engagement patterns
    """
    
    def __init__(self, db: AsyncSession):
        super().__init__("Hybrid Recommendation System")
        self.db = db
        self.user_repo = UserRepository(db)
        self.interaction_repo = InteractionRepository(db)
        
        # Initialize component algorithms
        self.content_based = ContentBasedRecommendation(db)
        self.collaborative = CollaborativeFilteringRecommendation(db, method="user_based")
        self.trending = TrendingRecommendation(db, trending_type="hot")
        
        # Default algorithm weights (will be adjusted dynamically)
        self.default_weights = {
            "content_based": 0.4,
            "collaborative": 0.3,
            "trending": 0.2,
            "diversity": 0.1  # Reserved for diversity boost
        }
        
        # Algorithm parameters
        self.min_interactions_for_personalization = 5
        self.diversity_threshold = 0.7  # Minimum diversity score
        self.max_algorithm_candidates = 50  # Max items from each algorithm
    
    async def generate_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs
    ) -> RecommendationResult:
        """
        Generate hybrid recommendations combining multiple algorithms.
        
        Args:
            user_id: User ID
            num_recommendations: Number of recommendations
            exclude_content_ids: Content to exclude
            **kwargs: Additional parameters
            
        Returns:
            RecommendationResult with hybrid recommendations
        """
        self.validate_user_id(user_id)
        self.validate_num_recommendations(num_recommendations)
        self.log_recommendation_request(user_id, num_recommendations, **kwargs)
        
        try:
            # Analyze user profile to determine algorithm weights
            user_profile = await self._analyze_user_profile(user_id)
            algorithm_weights = self._calculate_dynamic_weights(user_profile, **kwargs)
            
            # Get recommendations from each algorithm
            algorithm_results = await self._get_algorithm_recommendations(
                user_id,
                self.max_algorithm_candidates,
                exclude_content_ids,
                **kwargs
            )
            
            # Combine recommendations using weighted scoring
            combined_recommendations = self._combine_algorithm_results(
                algorithm_results,
                algorithm_weights
            )
            
            # Apply diversity optimization
            if self.diversity_threshold > 0:
                combined_recommendations = await self._optimize_diversity(
                    combined_recommendations,
                    user_profile
                )
            
            # Select top N recommendations
            final_recommendations = combined_recommendations[:num_recommendations]
            
            content_ids = [item[0] for item in final_recommendations]
            scores = [item[1] for item in final_recommendations]
            
            # Normalize scores to 0-1 range
            if scores:
                max_score = max(scores)
                scores = [score / max_score for score in scores]
            
            metadata = {
                "algorithm_weights": algorithm_weights,
                "user_profile_summary": {
                    "interaction_count": user_profile.get("total_interactions", 0),
                    "personalization_level": user_profile.get("personalization_level", "low"),
                    "primary_categories": user_profile.get("top_categories", [])[:3]
                },
                "algorithm_contributions": {
                    algo: len([r for r in algorithm_results[algo].content_ids if r in content_ids])
                    for algo in algorithm_results
                },
                "diversity_score": self._calculate_diversity_score(content_ids, []),
                "total_candidates_considered": sum(
                    len(result.content_ids) for result in algorithm_results.values()
                )
            }
            
            return RecommendationResult(
                content_ids=content_ids,
                scores=scores,
                algorithm_name=self.name,
                user_id=user_id,
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Error in hybrid recommendation for user {user_id}: {e}")
            # Fallback to trending content
            return await self._get_fallback_recommendations(user_id, num_recommendations)
    
    async def _analyze_user_profile(self, user_id: int) -> Dict[str, Any]:
        """
        Analyze user profile to determine recommendation strategy.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user profile analysis
        """
        try:
            # Get user's recommendation data
            user_data = await self.interaction_repo.get_user_recommendation_data(user_id)
            
            total_interactions = user_data.get("total_interactions", 0)
            
            # Determine personalization level
            if total_interactions < 3:
                personalization_level = "minimal"
            elif total_interactions < 20:
                personalization_level = "low"
            elif total_interactions < 50:
                personalization_level = "medium"
            else:
                personalization_level = "high"
            
            # Get user preferences
            preferred_content_types = user_data.get("preferred_content_types", [])
            
            # Calculate user engagement patterns
            interaction_summary = user_data.get("interaction_summary", {})
            engagement_diversity = len([k for k, v in interaction_summary.items() if v > 0])
            
            profile = {
                "user_id": user_id,
                "total_interactions": total_interactions,
                "personalization_level": personalization_level,
                "preferred_content_types": preferred_content_types,
                "engagement_diversity": engagement_diversity,
                "is_new_user": total_interactions < self.min_interactions_for_personalization,
                "is_active_user": total_interactions > 20,
                "interaction_summary": interaction_summary
            }
            
            return profile
            
        except Exception as e:
            self.logger.error(f"Error analyzing user profile for {user_id}: {e}")
            return {"user_id": user_id, "is_new_user": True, "personalization_level": "minimal"}
    
    def _calculate_dynamic_weights(
        self, 
        user_profile: Dict[str, Any], 
        **kwargs
    ) -> Dict[str, float]:
        """
        Calculate dynamic weights for algorithms based on user profile and context.
        
        Args:
            user_profile: User profile analysis
            **kwargs: Additional context (time, device, etc.)
            
        Returns:
            Dictionary with algorithm weights
        """
        weights = self.default_weights.copy()
        
        personalization_level = user_profile.get("personalization_level", "minimal")
        is_new_user = user_profile.get("is_new_user", True)
        
        # Adjust weights based on user data availability
        if is_new_user:
            # New users: rely more on trending, less on personalization
            weights["trending"] = 0.5
            weights["content_based"] = 0.2
            weights["collaborative"] = 0.1
            weights["diversity"] = 0.2
            
        elif personalization_level == "high":
            # Experienced users: focus on personalization
            weights["content_based"] = 0.5
            weights["collaborative"] = 0.4
            weights["trending"] = 0.05
            weights["diversity"] = 0.05
            
        elif personalization_level == "medium":
            # Balanced approach
            weights["content_based"] = 0.4
            weights["collaborative"] = 0.3
            weights["trending"] = 0.2
            weights["diversity"] = 0.1
        
        # Context-based adjustments
        current_hour = kwargs.get("current_hour", 12)
        
        # During peak hours, boost trending content
        if 18 <= current_hour <= 22:  # Evening hours
            weights["trending"] += 0.1
            weights["content_based"] -= 0.05
            weights["collaborative"] -= 0.05
        
        # Ensure weights sum to 1.0
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}
        
        return weights
    
    async def _get_algorithm_recommendations(
        self,
        user_id: int,
        num_candidates: int,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs
    ) -> Dict[str, RecommendationResult]:
        """
        Get recommendations from all component algorithms.
        
        Args:
            user_id: User ID
            num_candidates: Number of candidates from each algorithm
            exclude_content_ids: Content to exclude
            **kwargs: Additional parameters
            
        Returns:
            Dictionary mapping algorithm names to their results
        """
        results = {}
        
        try:
            # Content-based recommendations
            results["content_based"] = await self.content_based.generate_recommendations(
                user_id, num_candidates, exclude_content_ids, **kwargs
            )
        except Exception as e:
            self.logger.warning(f"Content-based algorithm failed: {e}")
            results["content_based"] = RecommendationResult([], [], "content_based", user_id)
        
        try:
            # Collaborative filtering recommendations
            results["collaborative"] = await self.collaborative.generate_recommendations(
                user_id, num_candidates, exclude_content_ids, **kwargs
            )
        except Exception as e:
            self.logger.warning(f"Collaborative filtering algorithm failed: {e}")
            results["collaborative"] = RecommendationResult([], [], "collaborative", user_id)
        
        try:
            # Trending recommendations
            results["trending"] = await self.trending.generate_recommendations(
                user_id, num_candidates, exclude_content_ids, **kwargs
            )
        except Exception as e:
            self.logger.warning(f"Trending algorithm failed: {e}")
            results["trending"] = RecommendationResult([], [], "trending", user_id)
        
        return results
    
    def _combine_algorithm_results(
        self,
        algorithm_results: Dict[str, RecommendationResult],
        weights: Dict[str, float]
    ) -> List[Tuple[int, float]]:
        """
        Combine results from multiple algorithms using weighted scoring.
        
        Args:
            algorithm_results: Results from each algorithm
            weights: Weight for each algorithm
            
        Returns:
            List of (content_id, combined_score) tuples, sorted by score
        """
        content_scores = {}
        content_algorithm_sources = {}
        
        # Combine scores from all algorithms
        for algo_name, result in algorithm_results.items():
            if algo_name not in weights:
                continue
                
            weight = weights[algo_name]
            
            for content_id, score in zip(result.content_ids, result.scores):
                if content_id not in content_scores:
                    content_scores[content_id] = 0
                    content_algorithm_sources[content_id] = []
                
                weighted_score = score * weight
                content_scores[content_id] += weighted_score
                content_algorithm_sources[content_id].append(algo_name)
        
        # Bonus for content recommended by multiple algorithms
        for content_id in content_scores:
            algorithm_count = len(content_algorithm_sources[content_id])
            if algorithm_count > 1:
                # Boost score for multi-algorithm consensus
                consensus_bonus = 0.1 * (algorithm_count - 1)
                content_scores[content_id] *= (1 + consensus_bonus)
        
        # Sort by combined score
        sorted_content = sorted(
            content_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_content
    
    async def _optimize_diversity(
        self,
        recommendations: List[Tuple[int, float]],
        user_profile: Dict[str, Any]
    ) -> List[Tuple[int, float]]:
        """
        Optimize recommendation diversity to avoid filter bubbles.
        
        Args:
            recommendations: List of (content_id, score) tuples
            user_profile: User profile information
            
        Returns:
            Diversity-optimized recommendations
        """
        if len(recommendations) <= 5:
            return recommendations  # Too few items to optimize
        
        # This is a simplified diversity optimization
        # In production, you'd use more sophisticated algorithms like MMR
        # (Maximal Marginal Relevance) or DPP (Determinantal Point Processes)
        
        optimized = []
        remaining = recommendations.copy()
        selected_categories = set()
        selected_content_types = set()
        
        # Select diverse items using greedy approach
        while len(optimized) < len(recommendations) and remaining:
            best_item = None
            best_score = -1
            
            for item in remaining:
                content_id, relevance_score = item
                
                # Get content metadata (simplified)
                # In production, you'd fetch actual content data
                diversity_bonus = 0
                
                # Simulate content metadata
                mock_category = content_id % 5  # Mock category
                mock_content_type = ["article", "video", "course"][content_id % 3]
                
                # Bonus for category diversity
                if mock_category not in selected_categories:
                    diversity_bonus += 0.2
                
                # Bonus for content type diversity
                if mock_content_type not in selected_content_types:
                    diversity_bonus += 0.1
                
                # Combined score = relevance + diversity
                combined_score = relevance_score + diversity_bonus
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_item = item
            
            if best_item:
                optimized.append(best_item)
                remaining.remove(best_item)
                
                # Update diversity tracking
                content_id = best_item[0]
                selected_categories.add(content_id % 5)
                selected_content_types.add(["article", "video", "course"][content_id % 3])
        
        return optimized
    
    def _calculate_diversity_score(self, content_ids: List[int], content_metadata: List[Dict]) -> float:
        """
        Calculate diversity score for a list of recommendations.
        
        Args:
            content_ids: List of recommended content IDs
            content_metadata: Metadata for content items (unused in simplified version)
            
        Returns:
            Diversity score between 0 and 1
        """
        if len(content_ids) <= 1:
            return 1.0
        
        # Simplified diversity calculation based on ID distribution
        # In production, you'd use actual content features like categories, topics, etc.
        unique_categories = len(set(content_id % 10 for content_id in content_ids))
        max_possible_categories = min(len(content_ids), 10)
        
        return unique_categories / max_possible_categories if max_possible_categories > 0 else 1.0
    
    async def _get_fallback_recommendations(
        self,
        user_id: int,
        num_recommendations: int
    ) -> RecommendationResult:
        """
        Fallback recommendations when main algorithm fails.
        
        Args:
            user_id: User ID
            num_recommendations: Number of recommendations
            
        Returns:
            Fallback recommendations (trending content)
        """
        try:
            fallback_trending = TrendingRecommendation(self.db, "hot")
            return await fallback_trending.generate_recommendations(
                user_id, num_recommendations
            )
        except Exception as e:
            self.logger.error(f"Fallback recommendations failed: {e}")
            # Ultimate fallback: empty recommendations
            return RecommendationResult([], [], f"{self.name} (Fallback)", user_id)
    
    async def explain_recommendation(
        self,
        user_id: int,
        content_id: int
    ) -> Dict[str, Any]:
        """
        Explain hybrid recommendation by showing contributing algorithms.
        
        Args:
            user_id: User ID
            content_id: Content ID to explain
            
        Returns:
            Multi-algorithm explanation
        """
        try:
            explanations = {}
            
            # Get explanation from each algorithm that might have contributed
            try:
                explanations["content_based"] = await self.content_based.explain_recommendation(
                    user_id, content_id
                )
            except Exception:
                pass
            
            try:
                explanations["collaborative"] = await self.collaborative.explain_recommendation(
                    user_id, content_id
                )
            except Exception:
                pass
            
            try:
                explanations["trending"] = await self.trending.explain_recommendation(
                    user_id, content_id
                )
            except Exception:
                pass
            
            # Combine explanations
            hybrid_explanation = {
                "content_id": content_id,
                "algorithm": "hybrid_recommendation",
                "overall_explanation": "This content was recommended by combining multiple recommendation approaches",
                "contributing_algorithms": [],
                "detailed_explanations": explanations
            }
            
            # Identify which algorithms contributed
            for algo_name, explanation in explanations.items():
                if "error" not in explanation:
                    hybrid_explanation["contributing_algorithms"].append(algo_name)
            
            # Generate combined explanation
            if len(hybrid_explanation["contributing_algorithms"]) > 1:
                hybrid_explanation["overall_explanation"] = (
                    f"Multiple algorithms agreed this content is relevant: "
                    f"{', '.join(hybrid_explanation['contributing_algorithms'])}"
                )
            elif len(hybrid_explanation["contributing_algorithms"]) == 1:
                algo_name = hybrid_explanation["contributing_algorithms"][0]
                hybrid_explanation["overall_explanation"] = (
                    f"Recommended primarily by {algo_name} algorithm"
                )
            
            return hybrid_explanation
            
        except Exception as e:
            self.logger.error(f"Error explaining hybrid recommendation: {e}")
            return {"error": "Unable to generate explanation"}


class ABTestingHybridRecommendation(HybridRecommendation):
    """
    Hybrid recommendation with A/B testing capabilities.
    
    This allows testing different algorithm combinations and weights
    to optimize recommendation performance.
    """
    
    def __init__(self, db: AsyncSession, experiment_config: Optional[Dict[str, Any]] = None):
        super().__init__(db)
        self.name = "A/B Testing Hybrid Recommendation"
        self.experiment_config = experiment_config or {}
    
    async def generate_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs
    ) -> RecommendationResult:
        """
        Generate recommendations with A/B testing.
        
        Users are randomly assigned to different algorithm variants
        to test which combinations perform better.
        """
        # Determine user's experiment variant
        variant = self._get_user_variant(user_id)
        
        # Apply variant-specific algorithm weights
        original_weights = self.default_weights.copy()
        
        if variant == "content_heavy":
            self.default_weights["content_based"] = 0.6
            self.default_weights["collaborative"] = 0.2
            self.default_weights["trending"] = 0.2
            
        elif variant == "collaborative_heavy":
            self.default_weights["content_based"] = 0.2
            self.default_weights["collaborative"] = 0.6
            self.default_weights["trending"] = 0.2
            
        elif variant == "trending_heavy":
            self.default_weights["content_based"] = 0.2
            self.default_weights["collaborative"] = 0.2
            self.default_weights["trending"] = 0.6
        
        try:
            # Generate recommendations with variant weights
            result = await super().generate_recommendations(
                user_id, num_recommendations, exclude_content_ids, **kwargs
            )
            
            # Add A/B testing metadata
            result.metadata["ab_test_variant"] = variant
            result.algorithm_name = f"{result.algorithm_name} (Variant: {variant})"
            
            return result
            
        finally:
            # Restore original weights
            self.default_weights = original_weights
    
    def _get_user_variant(self, user_id: int) -> str:
        """
        Assign user to A/B test variant based on user ID.
        
        Args:
            user_id: User ID
            
        Returns:
            Variant name
        """
        # Simple hash-based assignment for consistent variant assignment
        variants = ["control", "content_heavy", "collaborative_heavy", "trending_heavy"]
        variant_index = user_id % len(variants)
        return variants[variant_index]