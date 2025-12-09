"""
Analytics API endpoints for recommendation system insights.

This provides:
1. Recommendation history and tracking
2. Algorithm performance analytics
3. User interaction patterns
4. A/B testing results
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.content import Content
from app.models.recommendation_log import (
    AlgorithmPerformanceMetrics,
    RecommendationLog,
    RecommendationOutcome,
)
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/recommendations/history")
async def get_recommendation_history(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    algorithm: Optional[str] = Query(None, description="Filter by algorithm"),
    content_id: Optional[int] = Query(None, description="Filter by content ID"),
    days_back: int = Query(7, ge=1, le=365, description="Days to look back"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum results"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get recommendation history with filtering options.

    Shows which algorithms recommended which content to which users,
    along with user interactions and outcomes.
    """

    # Build the query with filters
    query = select(RecommendationLog).options(
        selectinload(RecommendationLog.user), selectinload(RecommendationLog.content)
    )

    # Apply filters
    filters = [
        RecommendationLog.created_at >= datetime.utcnow() - timedelta(days=days_back)
    ]

    if user_id:
        filters.append(RecommendationLog.user_id == user_id)
    if algorithm:
        filters.append(RecommendationLog.algorithm_name == algorithm)
    if content_id:
        filters.append(RecommendationLog.content_id == content_id)

    query = query.where(and_(*filters))
    query = query.order_by(desc(RecommendationLog.created_at))
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    recommendation_logs = result.scalars().all()

    # Format results
    history = []
    for log in recommendation_logs:
        history.append(
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_name": log.user.full_name if log.user else "Unknown",
                "content_id": log.content_id,
                "content_title": log.content.title if log.content else "Unknown",
                "algorithm_name": log.algorithm_name,
                "recommendation_score": log.recommendation_score,
                "position": log.position_in_results,
                "outcome": log.outcome,
                "explanation": log.explanation_shown,
                "interaction_time": (
                    log.interaction_timestamp.isoformat()
                    if log.interaction_timestamp
                    else None
                ),
                "time_to_interaction": log.time_to_interaction_seconds,
                "created_at": log.created_at.isoformat(),
                "cache_hit": log.cache_hit,
                "generation_time_ms": log.generation_time_ms,
            }
        )

    return {
        "history": history,
        "filters": {
            "user_id": user_id,
            "algorithm": algorithm,
            "content_id": content_id,
            "days_back": days_back,
        },
        "pagination": {"limit": limit, "skip": skip, "total": len(history)},
    }


@router.get("/algorithms/performance")
async def get_algorithm_performance(
    days_back: int = Query(7, ge=1, le=365, description="Days to analyze"),
    algorithm: Optional[str] = Query(None, description="Specific algorithm to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get algorithm performance metrics and comparisons.

    Shows click-through rates, engagement metrics, and other KPIs
    for each recommendation algorithm.
    """

    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    # Build base query
    query = select(
        RecommendationLog.algorithm_name,
        func.count(RecommendationLog.id).label("total_recommendations"),
        func.count(
            func.nullif(
                RecommendationLog.outcome == RecommendationOutcome.CLICKED, False
            )
        ).label("clicks"),
        func.count(
            func.nullif(RecommendationLog.outcome == RecommendationOutcome.LIKED, False)
        ).label("likes"),
        func.count(
            func.nullif(RecommendationLog.outcome == RecommendationOutcome.SAVED, False)
        ).label("saves"),
        func.count(
            func.nullif(
                RecommendationLog.outcome == RecommendationOutcome.DISMISSED, False
            )
        ).label("dismissals"),
        func.avg(RecommendationLog.recommendation_score).label("avg_score"),
        func.avg(RecommendationLog.generation_time_ms).label("avg_generation_time"),
        func.avg(RecommendationLog.time_to_interaction_seconds).label(
            "avg_interaction_time"
        ),
        func.count(func.distinct(RecommendationLog.content_id)).label("unique_content"),
    ).where(RecommendationLog.created_at >= cutoff_date)

    if algorithm:
        query = query.where(RecommendationLog.algorithm_name == algorithm)

    query = query.group_by(RecommendationLog.algorithm_name)
    query = query.order_by(desc("total_recommendations"))

    result = await db.execute(query)
    performance_data = result.fetchall()

    # Calculate derived metrics
    algorithms = []
    for row in performance_data:
        total_recs = row.total_recommendations or 0
        clicks = row.clicks or 0
        likes = row.likes or 0
        saves = row.saves or 0
        dismissals = row.dismissals or 0

        algorithms.append(
            {
                "algorithm_name": row.algorithm_name,
                "total_recommendations": total_recs,
                "clicks": clicks,
                "likes": likes,
                "saves": saves,
                "dismissals": dismissals,
                "click_through_rate": (
                    round(clicks / total_recs * 100, 2) if total_recs > 0 else 0
                ),
                "like_rate": (
                    round(likes / total_recs * 100, 2) if total_recs > 0 else 0
                ),
                "save_rate": (
                    round(saves / total_recs * 100, 2) if total_recs > 0 else 0
                ),
                "dismissal_rate": (
                    round(dismissals / total_recs * 100, 2) if total_recs > 0 else 0
                ),
                "engagement_rate": (
                    round((clicks + likes + saves) / total_recs * 100, 2)
                    if total_recs > 0
                    else 0
                ),
                "avg_recommendation_score": round(float(row.avg_score or 0), 3),
                "avg_generation_time_ms": round(float(row.avg_generation_time or 0), 2),
                "avg_interaction_time_seconds": round(
                    float(row.avg_interaction_time or 0), 2
                ),
                "unique_content_recommended": row.unique_content or 0,
            }
        )

    return {
        "performance_summary": algorithms,
        "analysis_period": {
            "days_back": days_back,
            "start_date": cutoff_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
        },
        "insights": _generate_performance_insights(algorithms),
    }


@router.get("/content/{content_id}/recommendations")
async def get_content_recommendation_history(
    content_id: int,
    days_back: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get recommendation history for specific content.

    Shows which algorithms recommended this content, to which users,
    and what the outcomes were.
    """

    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    # Get content info
    content_query = select(Content).where(Content.id == content_id)
    content_result = await db.execute(content_query)
    content = content_result.scalar_one_or_none()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Get recommendation history
    query = (
        select(
            RecommendationLog.algorithm_name,
            func.count(RecommendationLog.id).label("times_recommended"),
            func.count(
                func.nullif(
                    RecommendationLog.outcome == RecommendationOutcome.CLICKED, False
                )
            ).label("clicks"),
            func.count(
                func.nullif(
                    RecommendationLog.outcome == RecommendationOutcome.LIKED, False
                )
            ).label("likes"),
            func.avg(RecommendationLog.recommendation_score).label("avg_score"),
            func.avg(RecommendationLog.position_in_results).label("avg_position"),
        )
        .where(
            and_(
                RecommendationLog.content_id == content_id,
                RecommendationLog.created_at >= cutoff_date,
            )
        )
        .group_by(RecommendationLog.algorithm_name)
    )

    result = await db.execute(query)
    algorithm_stats = result.fetchall()

    # Format results
    algorithms = []
    total_recommendations = 0
    total_clicks = 0

    for row in algorithm_stats:
        times_recommended = row.times_recommended or 0
        clicks = row.clicks or 0
        likes = row.likes or 0

        total_recommendations += times_recommended
        total_clicks += clicks

        algorithms.append(
            {
                "algorithm_name": row.algorithm_name,
                "times_recommended": times_recommended,
                "clicks": clicks,
                "likes": likes,
                "click_through_rate": (
                    round(clicks / times_recommended * 100, 2)
                    if times_recommended > 0
                    else 0
                ),
                "like_rate": (
                    round(likes / times_recommended * 100, 2)
                    if times_recommended > 0
                    else 0
                ),
                "avg_recommendation_score": round(float(row.avg_score or 0), 3),
                "avg_position": round(float(row.avg_position or 0), 1),
            }
        )

    return {
        "content": {
            "id": content.id,
            "title": content.title,
            "content_type": content.content_type.value,
            "category": content.category.name if content.category else None,
            "view_count": content.view_count,
            "like_count": content.like_count,
        },
        "recommendation_stats": {
            "total_recommendations": total_recommendations,
            "total_clicks": total_clicks,
            "overall_ctr": (
                round(total_clicks / total_recommendations * 100, 2)
                if total_recommendations > 0
                else 0
            ),
            "algorithms": algorithms,
        },
        "analysis_period": {
            "days_back": days_back,
            "start_date": cutoff_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
        },
    }


@router.get("/users/{user_id}/recommendations")
async def get_user_recommendation_history(
    user_id: int,
    days_back: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get recommendation history for a specific user.

    Shows what algorithms have been recommending to this user
    and how they've been responding.
    """

    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    # Get user info
    user_query = select(User).where(User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get recommendation stats by algorithm
    query = (
        select(
            RecommendationLog.algorithm_name,
            func.count(RecommendationLog.id).label("recommendations_received"),
            func.count(
                func.nullif(
                    RecommendationLog.outcome == RecommendationOutcome.CLICKED, False
                )
            ).label("clicks"),
            func.count(
                func.nullif(
                    RecommendationLog.outcome == RecommendationOutcome.LIKED, False
                )
            ).label("likes"),
            func.count(
                func.nullif(
                    RecommendationLog.outcome == RecommendationOutcome.SAVED, False
                )
            ).label("saves"),
            func.count(func.distinct(RecommendationLog.content_id)).label(
                "unique_content"
            ),
            func.avg(RecommendationLog.recommendation_score).label("avg_score"),
        )
        .where(
            and_(
                RecommendationLog.user_id == user_id,
                RecommendationLog.created_at >= cutoff_date,
            )
        )
        .group_by(RecommendationLog.algorithm_name)
    )

    result = await db.execute(query)
    algorithm_stats = result.fetchall()

    # Format results
    algorithms = []
    for row in algorithm_stats:
        recs_received = row.recommendations_received or 0
        clicks = row.clicks or 0
        likes = row.likes or 0
        saves = row.saves or 0

        algorithms.append(
            {
                "algorithm_name": row.algorithm_name,
                "recommendations_received": recs_received,
                "clicks": clicks,
                "likes": likes,
                "saves": saves,
                "engagement_rate": (
                    round((clicks + likes + saves) / recs_received * 100, 2)
                    if recs_received > 0
                    else 0
                ),
                "unique_content_shown": row.unique_content or 0,
                "avg_recommendation_score": round(float(row.avg_score or 0), 3),
            }
        )

    return {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "total_interactions": user.total_interactions,
        },
        "recommendation_stats": algorithms,
        "analysis_period": {
            "days_back": days_back,
            "start_date": cutoff_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
        },
    }


def _generate_performance_insights(algorithms: List[Dict[str, Any]]) -> List[str]:
    """Generate insights from algorithm performance data."""
    insights = []

    if not algorithms:
        return ["No recommendation data available for the selected period."]

    # Find best performing algorithm
    best_ctr = max(algorithms, key=lambda x: x["click_through_rate"])
    if best_ctr["click_through_rate"] > 0:
        insights.append(
            f"{best_ctr['algorithm_name']} has the highest click-through rate at {best_ctr['click_through_rate']}%"
        )

    # Find most active algorithm
    most_active = max(algorithms, key=lambda x: x["total_recommendations"])
    insights.append(
        f"{most_active['algorithm_name']} generated the most recommendations ({most_active['total_recommendations']})"
    )

    # Performance comparison
    if len(algorithms) > 1:
        avg_ctr = sum(alg["click_through_rate"] for alg in algorithms) / len(algorithms)
        above_avg = [alg for alg in algorithms if alg["click_through_rate"] > avg_ctr]
        if above_avg:
            insights.append(
                f"{len(above_avg)} out of {len(algorithms)} algorithms are performing above average CTR ({avg_ctr:.1f}%)"
            )

    # Speed insights
    fastest = min(algorithms, key=lambda x: x["avg_generation_time_ms"])
    if fastest["avg_generation_time_ms"] > 0:
        insights.append(
            f"{fastest['algorithm_name']} is the fastest algorithm at {fastest['avg_generation_time_ms']:.1f}ms average"
        )

    return insights
