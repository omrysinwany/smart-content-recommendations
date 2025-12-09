"""
API endpoints for content recommendations.

This provides:
1. User personalized recommendations
2. Trending content endpoints
3. Similar content discovery
4. Recommendation explanations
5. Performance analytics and monitoring
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.recommendations import (
    PerformanceAnalytics,
    RecommendationFeedback,
    RecommendationResponse,
    SimilarContentRequest,
    TrendingRequest,
)
from app.services.performance_service import PerformanceService
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/user/{user_id}", response_model=RecommendationResponse)
async def get_user_recommendations(
    user_id: int = Path(..., description="User ID to get recommendations for"),
    algorithm: str = Query(
        "auto",
        description="Algorithm to use (auto, content_based, collaborative, hybrid, etc.)",
    ),
    num_recommendations: int = Query(
        10, ge=1, le=50, description="Number of recommendations (1-50)"
    ),
    exclude_content_ids: Optional[List[int]] = Query(
        None, description="Content IDs to exclude"
    ),
    context: Optional[str] = Query(
        None, description="Additional context (JSON string)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get personalized recommendations for a user.

    This endpoint uses multiple recommendation algorithms to provide
    personalized content suggestions based on the user's interaction history,
    preferences, and current context.

    **Algorithm Options:**
    - `auto`: Automatically select best algorithm based on user profile
    - `content_based`: Recommend based on content similarity
    - `collaborative`: Recommend based on similar users
    - `trending_hot`: Current popular content
    - `hybrid`: Combine multiple approaches
    - `ab_test`: A/B testing variant

    **Response includes:**
    - Recommended content with scores
    - Algorithm explanation
    - Recommendation metadata
    - Performance metrics
    """
    try:
        recommendation_service = RecommendationService(db)

        # Parse context if provided
        context_data = None
        if context:
            import json

            try:
                context_data = json.loads(context)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Invalid context JSON format"
                )

        # Generate recommendations
        result = await recommendation_service.get_user_recommendations(
            user_id=user_id,
            algorithm=algorithm,
            num_recommendations=num_recommendations,
            exclude_content_ids=exclude_content_ids,
            context=context_data,
        )

        return result

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/trending", response_model=RecommendationResponse)
async def get_trending_recommendations(
    trending_type: str = Query(
        "hot", description="Type of trending (hot, rising, fresh, viral)"
    ),
    num_recommendations: int = Query(
        20, ge=1, le=100, description="Number of recommendations"
    ),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    time_window_days: int = Query(1, ge=1, le=30, description="Time window in days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get trending content recommendations.

    This endpoint provides different types of trending content based on
    real-time engagement metrics and user interactions.

    **Trending Types:**
    - `hot`: Currently most active content
    - `rising`: Content with increasing popularity
    - `fresh`: Recently published content with good engagement
    - `viral`: Content with exponential growth in shares

    **Time Windows:**
    - Hot: 1 day (default)
    - Rising: 3 days comparison periods
    - Fresh: 7 days for new content
    - Viral: 1 day for rapid growth detection
    """
    try:
        valid_trending_types = ["hot", "rising", "fresh", "viral"]
        if trending_type not in valid_trending_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid trending type. Must be one of: {valid_trending_types}",
            )

        recommendation_service = RecommendationService(db)

        result = await recommendation_service.get_trending_recommendations(
            trending_type=trending_type,
            num_recommendations=num_recommendations,
            category_id=category_id,
            time_window_days=time_window_days,
        )

        return result

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/similar/{content_id}", response_model=RecommendationResponse)
async def get_similar_content(
    content_id: int = Path(..., description="Content ID to find similar items for"),
    num_recommendations: int = Query(
        10, ge=1, le=50, description="Number of similar items"
    ),
    user_id: Optional[int] = Query(None, description="User ID for personalization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get content similar to a specific piece of content.

    This endpoint finds content that is similar to the specified content
    based on content features, categories, tags, and user interaction patterns.

    **Similarity Calculation:**
    - Content features (title, description, tags)
    - Category and topic similarity
    - User engagement patterns
    - Collaborative signals from similar users

    **Personalization:**
    - If user_id provided: Personalized similarity based on user preferences
    - If no user_id: Generic similarity based on content features only
    """
    try:
        recommendation_service = RecommendationService(db)

        result = await recommendation_service.get_similar_content(
            content_id=content_id,
            num_recommendations=num_recommendations,
            user_id=user_id,
        )

        return result

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/explain/{user_id}/{content_id}")
async def explain_recommendation(
    user_id: int = Path(..., description="User ID"),
    content_id: int = Path(..., description="Content ID to explain"),
    algorithm: str = Query("auto", description="Algorithm used for recommendation"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Explain why specific content was recommended to a user.

    This endpoint provides detailed explanations for recommendation decisions,
    helping users understand why certain content was suggested and improving
    transparency in the recommendation system.

    **Explanation includes:**
    - Algorithm(s) that contributed to the recommendation
    - User profile factors that influenced the decision
    - Content features that matched user preferences
    - Similarity scores and reasoning
    - Alternative explanations from different algorithms
    """
    try:
        recommendation_service = RecommendationService(db)

        explanation = await recommendation_service.explain_recommendation(
            user_id=user_id, content_id=content_id, algorithm=algorithm
        )

        return explanation

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/feedback")
async def record_recommendation_feedback(
    feedback: RecommendationFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record user feedback on recommendations.

    This endpoint collects user feedback on recommended content to improve
    future recommendations and evaluate algorithm performance.

    **Feedback Types:**
    - `clicked`: User clicked on the recommendation
    - `liked`: User explicitly liked the content
    - `dismissed`: User dismissed the recommendation
    - `not_interested`: User indicated lack of interest
    - `reported`: User reported inappropriate content

    **Usage for ML:**
    - Feedback is used to train and improve recommendation algorithms
    - Click-through rates help evaluate algorithm performance
    - Negative feedback helps filter out inappropriate recommendations
    """
    try:
        recommendation_service = RecommendationService(db)

        result = await recommendation_service.record_recommendation_feedback(
            user_id=feedback.user_id,
            content_id=feedback.content_id,
            feedback_type=feedback.feedback_type,
            algorithm=feedback.algorithm,
            recommendation_id=feedback.recommendation_id,
        )

        return result

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/performance", response_model=PerformanceAnalytics)
async def get_recommendation_performance(
    algorithm: Optional[str] = Query(None, description="Specific algorithm to analyze"),
    days_back: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recommendation system performance analytics.

    This endpoint provides comprehensive analytics about recommendation
    algorithm performance, including engagement metrics, click-through rates,
    and system performance indicators.

    **Metrics included:**
    - Click-through rates by algorithm
    - User engagement rates
    - Algorithm diversity and coverage
    - Response times and system performance
    - A/B testing results

    **Use cases:**
    - Algorithm performance comparison
    - System optimization insights
    - A/B testing analysis
    - Business intelligence reporting
    """
    try:
        recommendation_service = RecommendationService(db)

        performance_data = await recommendation_service.get_recommendation_performance(
            algorithm=algorithm, days_back=days_back
        )

        return performance_data

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/system/health")
async def get_system_health(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get recommendation system health status.

    This endpoint provides real-time health information about the
    recommendation system, including cache performance, algorithm
    availability, and system resource usage.

    **Health indicators:**
    - Cache hit rates and performance
    - Algorithm response times
    - Database performance
    - System resource usage
    - Active alerts and issues
    """
    try:
        performance_service = PerformanceService(db)

        health_data = await performance_service.get_performance_dashboard()

        return {
            "status": (
                "healthy" if health_data["overview"]["status"] == "good" else "degraded"
            ),
            "timestamp": health_data["overview"]["last_updated"],
            "details": health_data,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.post("/system/optimize")
async def optimize_recommendation_system(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Trigger recommendation system optimization.

    This endpoint triggers automated optimization procedures for the
    recommendation system, including cache warming, performance tuning,
    and algorithm parameter adjustment.

    **Optimization actions:**
    - Cache warming for popular content
    - Algorithm weight adjustment
    - Database query optimization
    - Resource allocation optimization

    **Returns:**
    - List of optimization actions taken
    - Estimated performance improvements
    - Recommendations for manual optimizations
    """
    try:
        performance_service = PerformanceService(db)

        optimization_result = await performance_service.optimize_performance()

        return {
            "optimization_completed": True,
            "timestamp": "2025-01-19T10:30:00Z",
            "results": optimization_result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.get("/algorithms/info")
async def get_algorithm_information(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get information about available recommendation algorithms.

    This endpoint provides detailed information about all available
    recommendation algorithms, their capabilities, and recommended use cases.

    **Information includes:**
    - Algorithm descriptions and approaches
    - Strengths and limitations
    - Recommended use cases
    - Performance characteristics
    - Configuration parameters
    """
    try:
        algorithm_info = {
            "available_algorithms": {
                "content_based": {
                    "name": "Content-Based Filtering",
                    "description": "Recommends content similar to what the user has interacted with",
                    "strengths": [
                        "No cold start for items",
                        "Explainable recommendations",
                        "User independence",
                    ],
                    "limitations": [
                        "Limited discovery",
                        "Requires content features",
                        "Filter bubble risk",
                    ],
                    "use_cases": [
                        "New users with some interactions",
                        "Content-rich platforms",
                        "Niche interests",
                    ],
                },
                "collaborative": {
                    "name": "Collaborative Filtering",
                    "description": "Recommends content based on similar users' preferences",
                    "strengths": [
                        "Discovers diverse content",
                        "No content analysis needed",
                        "Leverages community wisdom",
                    ],
                    "limitations": [
                        "Cold start problem",
                        "Sparsity issues",
                        "Popularity bias",
                    ],
                    "use_cases": [
                        "Active user base",
                        "Social platforms",
                        "Diverse content catalogs",
                    ],
                },
                "trending": {
                    "name": "Trending Content",
                    "description": "Recommends currently popular or viral content",
                    "strengths": [
                        "No user data needed",
                        "Captures zeitgeist",
                        "High engagement",
                    ],
                    "limitations": [
                        "Not personalized",
                        "Popularity bias",
                        "Short-term focus",
                    ],
                    "use_cases": ["New users", "Breaking news", "Social media feeds"],
                },
                "hybrid": {
                    "name": "Hybrid Recommendation",
                    "description": "Combines multiple algorithms with dynamic weighting",
                    "strengths": ["Best of all approaches", "Adaptive", "Robust"],
                    "limitations": [
                        "Complex",
                        "Requires tuning",
                        "Higher computational cost",
                    ],
                    "use_cases": [
                        "Production systems",
                        "Diverse user base",
                        "Multiple content types",
                    ],
                },
            },
            "algorithm_selection_guide": {
                "new_users": ["trending", "hybrid"],
                "active_users": ["hybrid", "collaborative"],
                "content_creators": ["content_based", "trending"],
                "general_purpose": ["hybrid", "ab_test"],
            },
            "performance_characteristics": {
                "response_time_ms": {
                    "content_based": "50-150",
                    "collaborative": "100-300",
                    "trending": "20-80",
                    "hybrid": "150-400",
                },
                "cache_effectiveness": {
                    "content_based": "High",
                    "collaborative": "Medium",
                    "trending": "Very High",
                    "hybrid": "High",
                },
            },
        }

        return algorithm_info

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get algorithm info: {str(e)}"
        )
