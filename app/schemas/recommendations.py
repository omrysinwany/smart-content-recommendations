"""
Pydantic schemas for recommendation API endpoints.

This defines the data models for:
1. Recommendation requests and responses
2. Trending content schemas
3. Performance analytics models
4. Feedback and explanation schemas
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator


class RecommendationItem(BaseModel):
    """Individual recommendation item with content details."""
    
    content_id: int = Field(..., description="Unique content identifier")
    title: str = Field(..., description="Content title")
    description: Optional[str] = Field(None, description="Content description")
    content_type: str = Field(..., description="Type of content (article, video, course, etc.)")
    category: Optional[Dict[str, Any]] = Field(None, description="Content category information")
    author: Optional[str] = Field(None, description="Content author or creator")
    image_url: Optional[str] = Field(None, description="Content thumbnail or image URL")
    created_at: datetime = Field(..., description="Content creation timestamp")
    recommendation_score: float = Field(..., ge=0, le=1, description="Recommendation confidence score (0-1)")
    
    # Content statistics
    stats: Dict[str, Any] = Field(default_factory=dict, description="Content engagement statistics")
    
    # User-specific context (if available)
    user_context: Optional[Dict[str, Any]] = Field(None, description="User-specific interaction context")


class RecommendationResponse(BaseModel):
    """Response model for recommendation endpoints."""
    
    recommendations: List[RecommendationItem] = Field(..., description="List of recommended content")
    algorithm: str = Field(..., description="Algorithm used for recommendations")
    user_id: int = Field(..., description="User ID recommendations were generated for")
    generated_at: datetime = Field(..., description="Timestamp when recommendations were generated")
    total_items: int = Field(..., description="Total number of recommendations returned")
    
    # Algorithm metadata and explanation
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Algorithm-specific metadata")
    
    @validator('total_items', always=True)
    def validate_total_items(cls, v, values):
        """Ensure total_items matches recommendations list length."""
        if 'recommendations' in values:
            return len(values['recommendations'])
        return v


class TrendingRequest(BaseModel):
    """Request model for trending content."""
    
    trending_type: str = Field("hot", description="Type of trending (hot, rising, fresh, viral)")
    num_recommendations: int = Field(20, ge=1, le=100, description="Number of recommendations")
    category_id: Optional[int] = Field(None, description="Filter by category ID")
    time_window_days: int = Field(1, ge=1, le=30, description="Time window in days")
    
    @validator('trending_type')
    def validate_trending_type(cls, v):
        """Validate trending type is one of the allowed values."""
        allowed_types = ["hot", "rising", "fresh", "viral"]
        if v not in allowed_types:
            raise ValueError(f"trending_type must be one of {allowed_types}")
        return v


class SimilarContentRequest(BaseModel):
    """Request model for similar content recommendations."""
    
    content_id: int = Field(..., description="Content ID to find similar items for")
    num_recommendations: int = Field(10, ge=1, le=50, description="Number of similar items")
    user_id: Optional[int] = Field(None, description="User ID for personalization")


class RecommendationFeedback(BaseModel):
    """Model for recording user feedback on recommendations."""
    
    user_id: int = Field(..., description="User ID providing feedback")
    content_id: int = Field(..., description="Content ID being rated")
    feedback_type: str = Field(..., description="Type of feedback")
    algorithm: str = Field(..., description="Algorithm that generated the recommendation")
    recommendation_id: Optional[str] = Field(None, description="Recommendation batch ID for tracking")
    
    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        """Validate feedback type is one of the allowed values."""
        allowed_types = ["clicked", "liked", "dismissed", "not_interested", "reported"]
        if v not in allowed_types:
            raise ValueError(f"feedback_type must be one of {allowed_types}")
        return v


class AlgorithmPerformance(BaseModel):
    """Performance metrics for a specific algorithm."""
    
    recommendations_generated: int = Field(..., description="Total recommendations generated")
    click_through_rate: float = Field(..., ge=0, le=1, description="Click-through rate (0-1)")
    like_rate: float = Field(..., ge=0, le=1, description="Like rate (0-1)")
    dismissal_rate: float = Field(..., ge=0, le=1, description="Dismissal rate (0-1)")
    avg_relevance_score: float = Field(..., ge=0, le=1, description="Average relevance score")
    diversity_score: float = Field(..., ge=0, le=1, description="Content diversity score")
    coverage: float = Field(..., ge=0, le=1, description="Catalog coverage (fraction of content recommended)")
    novelty_score: float = Field(..., ge=0, le=1, description="Novelty score (how often new content is recommended)")


class PerformanceTimePeriod(BaseModel):
    """Time period for performance analysis."""
    
    start_date: datetime = Field(..., description="Analysis start date")
    end_date: datetime = Field(..., description="Analysis end date")
    days: int = Field(..., description="Number of days analyzed")


class OverallPerformance(BaseModel):
    """Overall system performance metrics."""
    
    total_users_served: int = Field(..., description="Total number of users served")
    avg_recommendations_per_user: float = Field(..., description="Average recommendations per user")
    user_engagement_rate: float = Field(..., ge=0, le=1, description="Overall user engagement rate")
    system_response_time_ms: float = Field(..., description="Average system response time in milliseconds")


class PerformanceAnalytics(BaseModel):
    """Complete performance analytics response."""
    
    time_period: PerformanceTimePeriod = Field(..., description="Analysis time period")
    algorithms: Dict[str, AlgorithmPerformance] = Field(..., description="Per-algorithm performance metrics")
    overall: OverallPerformance = Field(..., description="Overall system performance")


class ExplanationDetail(BaseModel):
    """Detailed explanation for a recommendation."""
    
    algorithm: str = Field(..., description="Algorithm that provided this explanation")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in this explanation")
    reasons: List[str] = Field(..., description="List of reasons for the recommendation")
    user_factors: Optional[Dict[str, Any]] = Field(None, description="User factors that influenced the recommendation")
    content_factors: Optional[Dict[str, Any]] = Field(None, description="Content factors that influenced the recommendation")


class RecommendationExplanation(BaseModel):
    """Complete explanation for why content was recommended."""
    
    content_id: int = Field(..., description="Content ID being explained")
    user_id: int = Field(..., description="User ID the recommendation was for")
    primary_algorithm: str = Field(..., description="Primary algorithm used")
    overall_explanation: str = Field(..., description="High-level explanation")
    confidence_score: float = Field(..., ge=0, le=1, description="Overall confidence in recommendation")
    
    # Detailed explanations from each contributing algorithm
    algorithm_explanations: List[ExplanationDetail] = Field(..., description="Detailed explanations by algorithm")
    
    # Content and user context
    content_details: Optional[Dict[str, Any]] = Field(None, description="Relevant content details")
    user_context: Optional[Dict[str, Any]] = Field(None, description="Relevant user context")


class SystemHealth(BaseModel):
    """System health status response."""
    
    status: str = Field(..., description="Overall system status (healthy, degraded, critical)")
    timestamp: datetime = Field(..., description="Health check timestamp")
    
    # Component health
    cache_status: str = Field(..., description="Cache system status")
    database_status: str = Field(..., description="Database status")
    algorithms_status: str = Field(..., description="Recommendation algorithms status")
    
    # Performance indicators
    cache_hit_rate: float = Field(..., ge=0, le=1, description="Current cache hit rate")
    avg_response_time_ms: float = Field(..., description="Average response time")
    active_alerts: int = Field(..., description="Number of active alerts")
    
    # Resource usage
    cpu_usage_percent: Optional[float] = Field(None, description="CPU usage percentage")
    memory_usage_percent: Optional[float] = Field(None, description="Memory usage percentage")


class OptimizationAction(BaseModel):
    """Individual optimization action taken."""
    
    action: str = Field(..., description="Action name")
    description: str = Field(..., description="Description of what was done")
    expected_impact: str = Field(..., description="Expected impact of the action")
    timestamp: datetime = Field(..., description="When the action was taken")


class OptimizationRecommendation(BaseModel):
    """Recommendation for manual optimization."""
    
    category: str = Field(..., description="Optimization category (database, cache, system, etc.)")
    action: str = Field(..., description="Recommended action")
    priority: str = Field(..., description="Priority level (low, medium, high, critical)")
    estimated_improvement: str = Field(..., description="Estimated improvement from this action")


class OptimizationResult(BaseModel):
    """Result of system optimization operation."""
    
    optimization_completed: bool = Field(..., description="Whether optimization completed successfully")
    timestamp: datetime = Field(..., description="Optimization completion timestamp")
    
    # Actions taken
    actions_taken: List[OptimizationAction] = Field(..., description="List of optimization actions taken")
    
    # Manual recommendations
    recommendations: List[OptimizationRecommendation] = Field(..., description="Recommendations for manual optimization")
    
    # Estimated improvements
    estimated_improvement: Dict[str, str] = Field(default_factory=dict, description="Estimated performance improvements")


class CacheStatistics(BaseModel):
    """Cache performance statistics."""
    
    total_operations: int = Field(..., description="Total cache operations")
    hits: int = Field(..., description="Cache hits")
    misses: int = Field(..., description="Cache misses")
    sets: int = Field(..., description="Cache sets")
    deletes: int = Field(..., description="Cache deletes")
    hit_rate: float = Field(..., ge=0, le=1, description="Cache hit rate")
    miss_rate: float = Field(..., ge=0, le=1, description="Cache miss rate")


class AlgorithmInfo(BaseModel):
    """Information about a recommendation algorithm."""
    
    name: str = Field(..., description="Algorithm name")
    description: str = Field(..., description="Algorithm description")
    strengths: List[str] = Field(..., description="Algorithm strengths")
    limitations: List[str] = Field(..., description="Algorithm limitations")
    use_cases: List[str] = Field(..., description="Recommended use cases")
    response_time_range: str = Field(..., description="Typical response time range")
    cache_effectiveness: str = Field(..., description="Cache effectiveness level")


class AlgorithmCatalog(BaseModel):
    """Complete catalog of available algorithms."""
    
    available_algorithms: Dict[str, AlgorithmInfo] = Field(..., description="Available recommendation algorithms")
    algorithm_selection_guide: Dict[str, List[str]] = Field(..., description="Algorithm selection recommendations by use case")
    performance_characteristics: Dict[str, Dict[str, str]] = Field(..., description="Performance characteristics comparison")


# Request/Response models for batch operations
class BatchRecommendationRequest(BaseModel):
    """Request model for batch recommendation generation."""
    
    user_ids: List[int] = Field(..., min_items=1, max_items=100, description="List of user IDs (1-100)")
    algorithm: str = Field("auto", description="Algorithm to use for all users")
    num_recommendations: int = Field(10, ge=1, le=50, description="Number of recommendations per user")
    
    @validator('user_ids')
    def validate_user_ids_unique(cls, v):
        """Ensure user IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("user_ids must be unique")
        return v


class BatchRecommendationResponse(BaseModel):
    """Response model for batch recommendation generation."""
    
    total_users: int = Field(..., description="Total number of users processed")
    successful_users: int = Field(..., description="Number of users successfully processed")
    failed_users: int = Field(..., description="Number of users that failed")
    results: Dict[int, RecommendationResponse] = Field(..., description="Recommendations by user ID")
    errors: Dict[int, str] = Field(default_factory=dict, description="Errors by user ID")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")