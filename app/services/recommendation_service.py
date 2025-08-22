"""
Recommendation Service - Business logic for content recommendations.

This provides:
1. High-level recommendation generation interface
2. Algorithm selection and orchestration
3. Recommendation caching and performance optimization
4. A/B testing and algorithm evaluation
5. Recommendation explanation and feedback processing
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.algorithms.content_based import ContentBasedRecommendation
from app.algorithms.collaborative_filtering import CollaborativeFilteringRecommendation
from app.algorithms.trending import TrendingRecommendation
from app.algorithms.hybrid import HybridRecommendation, ABTestingHybridRecommendation
from app.repositories.content_repository import ContentRepository
from app.repositories.user_repository import UserRepository
from app.repositories.interaction_repository import InteractionRepository
from app.core.exceptions import ValidationError, NotFoundError
from app.core.cache import cache_manager, cached, cache_invalidator
from app.models.interaction import InteractionType


class RecommendationService(BaseService):
    """
    Main recommendation service coordinating all recommendation algorithms.
    
    This service provides:
    - Multiple recommendation strategies (content-based, collaborative, trending, hybrid)
    - Intelligent algorithm selection based on user profile and context
    - Recommendation caching for performance
    - A/B testing capabilities for algorithm optimization
    - Recommendation explanation and user feedback processing
    """
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.content_repo = ContentRepository(db)
        self.user_repo = UserRepository(db)
        self.interaction_repo = InteractionRepository(db)
        
        # Initialize recommendation algorithms
        self.algorithms = {
            "content_based": ContentBasedRecommendation(db),
            "collaborative": CollaborativeFilteringRecommendation(db),
            "trending_hot": TrendingRecommendation(db, "hot"),
            "trending_rising": TrendingRecommendation(db, "rising"),
            "trending_fresh": TrendingRecommendation(db, "fresh"),
            "trending_viral": TrendingRecommendation(db, "viral"),
            "hybrid": HybridRecommendation(db),
            "ab_test": ABTestingHybridRecommendation(db)
        }
        
        # Service configuration
        self.default_algorithm = "hybrid"
        self.cache_ttl_minutes = 30  # Cache recommendations for 30 minutes
        self.max_recommendations = 50
        self.enable_ab_testing = True
    
    @cached(
        key_func=lambda self, user_id, algorithm="auto", num_recommendations=10, **kwargs: 
            f"user_rec:{user_id}:{algorithm}:{num_recommendations}",
        ttl=1800,  # 30 minutes
        namespace="recommendations",
        cache_layer="warm"
    )
    async def get_user_recommendations(
        self,
        user_id: int,
        algorithm: str = "auto",
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get personalized recommendations for a user.
        
        Args:
            user_id: User ID to generate recommendations for
            algorithm: Algorithm to use ("auto", "content_based", "collaborative", etc.)
            num_recommendations: Number of recommendations to return
            exclude_content_ids: Content IDs to exclude from recommendations
            context: Additional context (time, device, location, etc.)
            
        Returns:
            Dictionary with recommendations and metadata
            
        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If user doesn't exist
        """
        self._log_operation("get_user_recommendations", user_id=user_id, algorithm=algorithm)
        
        try:
            # Validate inputs
            await self._validate_recommendation_request(user_id, algorithm, num_recommendations)
            
            # Check cache first (in production, you'd use Redis)
            # cache_key = f"rec:{user_id}:{algorithm}:{num_recommendations}"
            # cached_result = await self._get_cached_recommendations(cache_key)
            # if cached_result:
            #     return cached_result
            
            # Select algorithm based on user profile and context
            selected_algorithm = await self._select_algorithm(user_id, algorithm, context)
            
            # Generate recommendations
            recommendation_result = await selected_algorithm.generate_recommendations(
                user_id=user_id,
                num_recommendations=num_recommendations,
                exclude_content_ids=exclude_content_ids,
                **(context or {})
            )
            
            # Enrich recommendations with content details
            enriched_recommendations = await self._enrich_recommendations(
                recommendation_result,
                user_id
            )
            
            # Log recommendation event for analytics
            await self._log_recommendation_event(user_id, enriched_recommendations)
            
            # Cache results (in production)
            # await self._cache_recommendations(cache_key, enriched_recommendations)
            
            return enriched_recommendations
            
        except Exception as error:
            await self._handle_service_error(error, "get user recommendations")
    
    @cached(
        key_func=lambda self, trending_type="hot", num_recommendations=20, category_id=None, time_window_days=1:
            f"trending:{trending_type}:{num_recommendations}:{category_id}:{time_window_days}",
        ttl=300,  # 5 minutes for trending content
        namespace="trending",
        cache_layer="hot"
    )
    async def get_trending_recommendations(
        self,
        trending_type: str = "hot",
        num_recommendations: int = 20,
        category_id: Optional[int] = None,
        time_window_days: int = 1
    ) -> Dict[str, Any]:
        """
        Get trending content recommendations.
        
        Args:
            trending_type: Type of trending ("hot", "rising", "fresh", "viral")
            num_recommendations: Number of recommendations
            category_id: Optional category filter
            time_window_days: Time window for trending calculation
            
        Returns:
            Trending recommendations with metadata
        """
        self._log_operation("get_trending_recommendations", trending_type=trending_type)
        
        try:
            # Get trending algorithm
            algorithm_key = f"trending_{trending_type}"
            if algorithm_key not in self.algorithms:
                algorithm_key = "trending_hot"  # Fallback
            
            trending_algorithm = self.algorithms[algorithm_key]
            
            # Generate trending recommendations
            # For trending, we use a dummy user_id since it's not personalized
            dummy_user_id = 0
            
            recommendation_result = await trending_algorithm.generate_recommendations(
                user_id=dummy_user_id,
                num_recommendations=num_recommendations,
                category_filter=category_id,
                time_window_days=time_window_days
            )
            
            # Enrich with content details
            enriched_recommendations = await self._enrich_recommendations(
                recommendation_result,
                user_id=None  # No user context for trending
            )
            
            return enriched_recommendations
            
        except Exception as error:
            await self._handle_service_error(error, "get trending recommendations")
    
    async def get_similar_content(
        self,
        content_id: int,
        num_recommendations: int = 10,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get content similar to a specific piece of content.
        
        Args:
            content_id: Reference content ID
            num_recommendations: Number of similar items to return
            user_id: Optional user ID for personalization
            
        Returns:
            Similar content recommendations
        """
        self._log_operation("get_similar_content", content_id=content_id)
        
        try:
            # Validate content exists
            content_detail = await self.content_repo.get_content_with_stats(content_id)
            if not content_detail:
                raise NotFoundError("Content not found")
            
            # Get similar content using content-based algorithm
            content_based_algo = self.algorithms["content_based"]
            
            # For similar content, we create a mock user profile based on this content
            if user_id:
                recommendation_result = await content_based_algo.generate_recommendations(
                    user_id=user_id,
                    num_recommendations=num_recommendations,
                    exclude_content_ids=[content_id],
                    similar_to_content_id=content_id  # Custom parameter
                )
            else:
                # Use repository method for non-personalized similarity
                similar_content = await self.content_repo.get_similar_content(
                    content_id, 
                    limit=num_recommendations
                )
                
                # Convert to recommendation result format
                content_ids = [c.id for c in similar_content]
                scores = [1.0 - (i * 0.1) for i in range(len(content_ids))]  # Mock scores
                
                from app.algorithms.base import RecommendationResult
                recommendation_result = RecommendationResult(
                    content_ids=content_ids,
                    scores=scores,
                    algorithm_name="Content Similarity",
                    user_id=user_id or 0,
                    metadata={"reference_content_id": content_id}
                )
            
            # Enrich recommendations
            enriched_recommendations = await self._enrich_recommendations(
                recommendation_result,
                user_id
            )
            
            return enriched_recommendations
            
        except Exception as error:
            await self._handle_service_error(error, "get similar content")
    
    async def explain_recommendation(
        self,
        user_id: int,
        content_id: int,
        algorithm: str = "auto"
    ) -> Dict[str, Any]:
        """
        Explain why specific content was recommended to a user.
        
        Args:
            user_id: User ID
            content_id: Content ID to explain
            algorithm: Algorithm used for the recommendation
            
        Returns:
            Detailed explanation of the recommendation
        """
        self._log_operation("explain_recommendation", user_id=user_id, content_id=content_id)
        
        try:
            # Select the algorithm that was used
            selected_algorithm = await self._select_algorithm(user_id, algorithm)
            
            # Get explanation from the algorithm
            explanation = await selected_algorithm.explain_recommendation(user_id, content_id)
            
            # Enrich explanation with content details
            content_detail = await self.content_repo.get_content_with_stats(content_id)
            if content_detail:
                explanation["content_details"] = {
                    "title": content_detail["content"]["title"],
                    "content_type": content_detail["content"]["content_type"],
                    "category": content_detail["content"].get("category", {}),
                    "stats": content_detail["stats"]
                }
            
            # Add user context
            user_profile = await self.interaction_repo.get_user_recommendation_data(user_id)
            explanation["user_context"] = {
                "total_interactions": user_profile.get("total_interactions", 0),
                "preferred_content_types": user_profile.get("preferred_content_types", [])[:3]
            }
            
            return explanation
            
        except Exception as error:
            await self._handle_service_error(error, "explain recommendation")
    
    async def record_recommendation_feedback(
        self,
        user_id: int,
        content_id: int,
        feedback_type: str,
        algorithm: str,
        recommendation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record user feedback on recommendations for algorithm improvement.
        
        Args:
            user_id: User ID
            content_id: Content ID that was recommended
            feedback_type: Type of feedback ("clicked", "liked", "dismissed", "reported")
            algorithm: Algorithm that generated the recommendation
            recommendation_id: Optional recommendation batch ID for tracking
            
        Returns:
            Feedback processing result
        """
        self._log_operation("record_recommendation_feedback", 
                          user_id=user_id, feedback_type=feedback_type)
        
        try:
            # Validate feedback type
            valid_feedback_types = ["clicked", "liked", "dismissed", "reported", "not_interested"]
            if feedback_type not in valid_feedback_types:
                raise ValidationError(f"Invalid feedback type: {feedback_type}")
            
            # Process different types of feedback
            if feedback_type == "clicked":
                # Record as view interaction
                await self.interaction_repo.create_or_update_interaction(
                    user_id, content_id, InteractionType.VIEW
                )
                
            elif feedback_type == "liked":
                # Record as like interaction
                await self.interaction_repo.create_or_update_interaction(
                    user_id, content_id, InteractionType.LIKE
                )
            
            elif feedback_type in ["dismissed", "not_interested"]:
                # Record negative feedback (would be stored in a feedback table)
                # This helps improve future recommendations
                pass
            
            elif feedback_type == "reported":
                # Handle content reporting
                pass
            
            # Log feedback for algorithm learning
            feedback_data = {
                "user_id": user_id,
                "content_id": content_id,
                "feedback_type": feedback_type,
                "algorithm": algorithm,
                "recommendation_id": recommendation_id,
                "timestamp": datetime.utcnow()
            }
            
            # In production, this would be stored in a feedback table
            # for machine learning model training
            self.logger.info(f"Recommendation feedback recorded: {feedback_data}")
            
            return {
                "success": True,
                "message": f"Feedback '{feedback_type}' recorded successfully",
                "feedback_data": feedback_data
            }
            
        except Exception as error:
            await self._handle_service_error(error, "record recommendation feedback")
    
    async def get_recommendation_performance(
        self,
        algorithm: Optional[str] = None,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """
        Get recommendation algorithm performance metrics.
        
        Args:
            algorithm: Specific algorithm to analyze (None for all)
            days_back: Number of days to analyze
            
        Returns:
            Performance metrics and analytics
        """
        self._log_operation("get_recommendation_performance", algorithm=algorithm)
        
        try:
            # This would typically query recommendation logs and feedback data
            # For demo, return mock performance metrics
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            performance_data = {
                "time_period": {
                    "start_date": cutoff_date.isoformat(),
                    "end_date": datetime.utcnow().isoformat(),
                    "days": days_back
                },
                "algorithms": {}
            }
            
            # Mock performance metrics for each algorithm
            algorithms_to_analyze = [algorithm] if algorithm else list(self.algorithms.keys())
            
            for algo_name in algorithms_to_analyze:
                performance_data["algorithms"][algo_name] = {
                    "recommendations_generated": 1250,  # Mock data
                    "click_through_rate": 0.15,
                    "like_rate": 0.08,
                    "dismissal_rate": 0.05,
                    "avg_relevance_score": 0.72,
                    "diversity_score": 0.68,
                    "coverage": 0.45,  # Fraction of content catalog recommended
                    "novelty_score": 0.62  # How often it recommends new content
                }
            
            # Overall system metrics
            performance_data["overall"] = {
                "total_users_served": 450,
                "avg_recommendations_per_user": 8.2,
                "user_engagement_rate": 0.34,
                "system_response_time_ms": 125
            }
            
            return performance_data
            
        except Exception as error:
            await self._handle_service_error(error, "get recommendation performance")
    
    # Private helper methods
    
    async def _validate_recommendation_request(
        self,
        user_id: int,
        algorithm: str,
        num_recommendations: int
    ) -> None:
        """Validate recommendation request parameters."""
        # Validate user exists
        user = await self.user_repo.get(user_id)
        if not user or not user.is_active:
            raise NotFoundError("User not found or inactive")
        
        # Validate algorithm
        if algorithm != "auto" and algorithm not in self.algorithms:
            raise ValidationError(f"Unknown algorithm: {algorithm}")
        
        # Validate num_recommendations
        if num_recommendations <= 0 or num_recommendations > self.max_recommendations:
            raise ValidationError(f"num_recommendations must be between 1 and {self.max_recommendations}")
    
    async def _select_algorithm(
        self,
        user_id: int,
        algorithm: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Select the best algorithm for the user and context."""
        if algorithm != "auto":
            return self.algorithms[algorithm]
        
        # Auto-select based on user profile and context
        user_data = await self.interaction_repo.get_user_recommendation_data(user_id)
        total_interactions = user_data.get("total_interactions", 0)
        
        # Algorithm selection logic
        if total_interactions < 5:
            # New users: use trending + some personalization
            return self.algorithms["trending_hot"]
                
        elif total_interactions < 20:
            # Growing users: hybrid approach
            return self.algorithms["hybrid"]
            
        else:
            # Experienced users: full personalization with A/B testing
            if self.enable_ab_testing:
                return self.algorithms["ab_test"]
            else:
                return self.algorithms["hybrid"]
    
    async def _enrich_recommendations(
        self,
        recommendation_result,
        user_id: Optional[int]
    ) -> Dict[str, Any]:
        """Enrich recommendations with content details and user context."""
        enriched_items = []
        
        for i, content_id in enumerate(recommendation_result.content_ids):
            score = recommendation_result.scores[i] if i < len(recommendation_result.scores) else 0
            
            # Get content details
            content_detail = await self.content_repo.get_content_with_stats(content_id)
            
            if content_detail:
                content_info = content_detail["content"]
                stats = content_detail["stats"]
                
                enriched_item = {
                    "content_id": content_id,
                    "title": content_info["title"],
                    "description": content_info["description"],
                    "content_type": content_info["content_type"],
                    "category": content_info.get("category"),
                    "author": content_info.get("author"),
                    "image_url": content_info.get("image_url"),
                    "created_at": content_info["created_at"],
                    "stats": stats,
                    "recommendation_score": score
                }
                
                # Add user-specific context if available
                if user_id:
                    user_interactions = await self.interaction_repo.get_user_content_interactions(
                        user_id, content_id
                    )
                    enriched_item["user_context"] = user_interactions
                
                enriched_items.append(enriched_item)
        
        return {
            "recommendations": enriched_items,
            "algorithm": recommendation_result.algorithm_name,
            "user_id": recommendation_result.user_id,
            "generated_at": recommendation_result.generated_at.isoformat(),
            "metadata": recommendation_result.metadata,
            "total_items": len(enriched_items)
        }
    
    async def _log_recommendation_event(
        self,
        user_id: int,
        recommendations: Dict[str, Any]
    ) -> None:
        """Log recommendation event for analytics."""
        event_data = {
            "user_id": user_id,
            "algorithm": recommendations["algorithm"],
            "num_recommendations": recommendations["total_items"],
            "timestamp": datetime.utcnow(),
            "content_ids": [item["content_id"] for item in recommendations["recommendations"]]
        }
        
        # In production, this would go to an analytics system
        self.logger.info(f"Recommendation event: {event_data}")
    
    def _get_algorithm_info(self) -> Dict[str, Any]:
        """Get information about all available algorithms."""
        algorithm_info = {}
        
        for name, algorithm in self.algorithms.items():
            algorithm_info[name] = algorithm.get_algorithm_info()
        
        return algorithm_info