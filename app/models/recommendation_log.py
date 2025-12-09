"""
Recommendation Log Model - Track which algorithms recommended which content to users.

This provides:
1. Track recommendation events and algorithm performance
2. A/B testing support for algorithm comparison
3. User interaction tracking with recommended content
4. Analytics for recommendation effectiveness
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class RecommendationOutcome(str, Enum):
    """Possible outcomes for recommended content."""

    SHOWN = "shown"  # Content was displayed to user
    CLICKED = "clicked"  # User clicked on the content
    LIKED = "liked"  # User liked the content
    SAVED = "saved"  # User saved the content
    SHARED = "shared"  # User shared the content
    DISMISSED = "dismissed"  # User explicitly dismissed the recommendation
    IGNORED = "ignored"  # Content was shown but user didn't interact


class RecommendationLog(Base):
    """
    Log of all recommendation events for analytics and debugging.

    This model tracks:
    - Which algorithm generated each recommendation
    - User interactions with recommendations
    - Algorithm performance metrics
    - A/B testing data
    """

    __tablename__ = "recommendation_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Core recommendation data
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    algorithm_name = Column(String(50), nullable=False, index=True)
    recommendation_score = Column(Float, nullable=False)
    position_in_results = Column(Integer, nullable=False)  # 1st, 2nd, 3rd, etc.

    # Session and context information
    session_id = Column(String(100), nullable=True, index=True)
    request_id = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True)

    # Algorithm metadata
    algorithm_version = Column(String(20), default="1.0.0")
    algorithm_metadata = Column(JSON, nullable=True)  # Algorithm-specific data

    # User interaction tracking
    outcome = Column(String(20), default=RecommendationOutcome.SHOWN, index=True)
    interaction_timestamp = Column(DateTime, nullable=True)
    time_to_interaction_seconds = Column(Float, nullable=True)

    # A/B Testing support
    ab_test_group = Column(String(50), nullable=True, index=True)
    ab_test_variant = Column(String(50), nullable=True)

    # Performance metrics
    generation_time_ms = Column(Float, nullable=True)
    cache_hit = Column(Boolean, default=False)

    # Additional context
    context_data = Column(JSON, nullable=True)  # Device, time, location, etc.
    explanation_shown = Column(Text, nullable=True)  # What explanation was shown

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="recommendation_logs")
    content = relationship("Content", back_populates="recommendation_logs")

    def __repr__(self):
        return f"<RecommendationLog(user_id={self.user_id}, content_id={self.content_id}, algorithm={self.algorithm_name}, outcome={self.outcome})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content_id": self.content_id,
            "algorithm_name": self.algorithm_name,
            "recommendation_score": self.recommendation_score,
            "position_in_results": self.position_in_results,
            "outcome": self.outcome,
            "interaction_timestamp": (
                self.interaction_timestamp.isoformat()
                if self.interaction_timestamp
                else None
            ),
            "time_to_interaction_seconds": self.time_to_interaction_seconds,
            "ab_test_group": self.ab_test_group,
            "generation_time_ms": self.generation_time_ms,
            "cache_hit": self.cache_hit,
            "explanation_shown": self.explanation_shown,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def create_recommendation_event(
        cls,
        user_id: int,
        content_id: int,
        algorithm_name: str,
        recommendation_score: float,
        position_in_results: int,
        **kwargs,
    ) -> "RecommendationLog":
        """
        Create a new recommendation log entry.

        Args:
            user_id: ID of user who received recommendation
            content_id: ID of recommended content
            algorithm_name: Name of algorithm that made recommendation
            recommendation_score: Algorithm's confidence score
            position_in_results: Position in recommendation list (1-based)
            **kwargs: Additional metadata

        Returns:
            New RecommendationLog instance
        """
        return cls(
            user_id=user_id,
            content_id=content_id,
            algorithm_name=algorithm_name,
            recommendation_score=recommendation_score,
            position_in_results=position_in_results,
            **kwargs,
        )

    def update_interaction(
        self,
        outcome: RecommendationOutcome,
        interaction_timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Update the recommendation with user interaction data.

        Args:
            outcome: What the user did with the recommendation
            interaction_timestamp: When the interaction occurred
        """
        self.outcome = outcome
        self.interaction_timestamp = interaction_timestamp or datetime.utcnow()

        # Calculate time to interaction
        if self.created_at and self.interaction_timestamp:
            time_diff = self.interaction_timestamp - self.created_at
            self.time_to_interaction_seconds = time_diff.total_seconds()

        self.updated_at = datetime.utcnow()


class AlgorithmPerformanceMetrics(Base):
    """
    Aggregated performance metrics for recommendation algorithms.

    This table stores periodic snapshots of algorithm performance
    for faster analytics queries.
    """

    __tablename__ = "algorithm_performance_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Algorithm identification
    algorithm_name = Column(String(50), nullable=False, index=True)
    algorithm_version = Column(String(20), default="1.0.0")

    # Time period for metrics
    date = Column(DateTime, nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # "hour", "day", "week"

    # Performance metrics
    total_recommendations = Column(Integer, default=0)
    total_interactions = Column(Integer, default=0)
    click_through_rate = Column(Float, default=0.0)
    like_rate = Column(Float, default=0.0)
    save_rate = Column(Float, default=0.0)
    share_rate = Column(Float, default=0.0)
    dismissal_rate = Column(Float, default=0.0)

    # Quality metrics
    avg_recommendation_score = Column(Float, default=0.0)
    avg_time_to_interaction = Column(Float, default=0.0)
    avg_generation_time_ms = Column(Float, default=0.0)
    cache_hit_rate = Column(Float, default=0.0)

    # Diversity and coverage metrics
    unique_content_recommended = Column(Integer, default=0)
    content_catalog_coverage = Column(Float, default=0.0)  # % of catalog recommended

    # A/B testing metrics
    ab_test_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AlgorithmPerformanceMetrics(algorithm={self.algorithm_name}, date={self.date}, ctr={self.click_through_rate:.3f})>"
