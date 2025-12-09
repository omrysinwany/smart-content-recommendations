"""
Performance monitoring and optimization service.

This provides:
1. Real-time performance metrics collection
2. Cache performance analysis
3. Database query optimization tracking
4. API response time monitoring
5. Automated performance alerts
"""

import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import cache_manager
from app.services.base import BaseService


class PerformanceMonitor:
    """
    Real-time performance monitoring system.

    Tracks various performance metrics and provides insights
    for optimization opportunities.
    """

    def __init__(self):
        """Initialize performance monitoring."""
        self.metrics = {
            "api_response_times": deque(maxlen=1000),  # Last 1000 API calls
            "database_query_times": deque(maxlen=1000),
            "cache_operations": deque(maxlen=1000),
            "recommendation_generation_times": deque(maxlen=100),
            "system_resources": deque(maxlen=100),
        }

        self.performance_thresholds = {
            "api_response_time_ms": 500,  # 500ms max response time
            "db_query_time_ms": 100,  # 100ms max query time
            "cache_hit_rate": 0.8,  # 80% minimum hit rate
            "memory_usage_percent": 80,  # 80% max memory usage
            "cpu_usage_percent": 70,  # 70% max CPU usage
        }

        self.alerts = []
        self.monitoring_enabled = True

    def track_api_call(self, endpoint: str, response_time: float, status_code: int):
        """
        Track API call performance.

        Args:
            endpoint: API endpoint called
            response_time: Response time in milliseconds
            status_code: HTTP status code
        """
        if not self.monitoring_enabled:
            return

        metric = {
            "timestamp": datetime.utcnow(),
            "endpoint": endpoint,
            "response_time_ms": response_time * 1000,  # Convert to ms
            "status_code": status_code,
        }

        self.metrics["api_response_times"].append(metric)

        # Check for performance threshold violations
        if response_time * 1000 > self.performance_thresholds["api_response_time_ms"]:
            self._create_alert(
                "api_response_time",
                {
                    "endpoint": endpoint,
                    "response_time_ms": response_time * 1000,
                    "threshold_ms": self.performance_thresholds["api_response_time_ms"],
                },
            )

    def track_database_query(self, query_type: str, execution_time: float):
        """
        Track database query performance.

        Args:
            query_type: Type of query (SELECT, INSERT, UPDATE, etc.)
            execution_time: Query execution time in milliseconds
        """
        if not self.monitoring_enabled:
            return

        metric = {
            "timestamp": datetime.utcnow(),
            "query_type": query_type,
            "execution_time_ms": execution_time * 1000,
        }

        self.metrics["database_query_times"].append(metric)

        # Check for slow query threshold
        if execution_time * 1000 > self.performance_thresholds["db_query_time_ms"]:
            self._create_alert(
                "slow_database_query",
                {
                    "query_type": query_type,
                    "execution_time_ms": execution_time * 1000,
                    "threshold_ms": self.performance_thresholds["db_query_time_ms"],
                },
            )

    def track_cache_operation(self, operation: str, hit: bool, response_time: float):
        """
        Track cache operation performance.

        Args:
            operation: Cache operation (get, set, delete)
            hit: Whether it was a cache hit (for get operations)
            response_time: Operation response time in milliseconds
        """
        if not self.monitoring_enabled:
            return

        metric = {
            "timestamp": datetime.utcnow(),
            "operation": operation,
            "hit": hit,
            "response_time_ms": response_time * 1000,
        }

        self.metrics["cache_operations"].append(metric)

    def track_recommendation_generation(
        self, algorithm: str, user_id: int, generation_time: float
    ):
        """
        Track recommendation generation performance.

        Args:
            algorithm: Recommendation algorithm used
            user_id: User ID recommendations were generated for
            generation_time: Time to generate recommendations in seconds
        """
        if not self.monitoring_enabled:
            return

        metric = {
            "timestamp": datetime.utcnow(),
            "algorithm": algorithm,
            "user_id": user_id,
            "generation_time_ms": generation_time * 1000,
        }

        self.metrics["recommendation_generation_times"].append(metric)

    def track_system_resources(self):
        """Track system resource usage."""
        if not self.monitoring_enabled:
            return

        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage("/").percent

        metric = {
            "timestamp": datetime.utcnow(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
        }

        self.metrics["system_resources"].append(metric)

        # Check resource thresholds
        if cpu_percent > self.performance_thresholds["cpu_usage_percent"]:
            self._create_alert(
                "high_cpu_usage",
                {
                    "cpu_percent": cpu_percent,
                    "threshold": self.performance_thresholds["cpu_usage_percent"],
                },
            )

        if memory_percent > self.performance_thresholds["memory_usage_percent"]:
            self._create_alert(
                "high_memory_usage",
                {
                    "memory_percent": memory_percent,
                    "threshold": self.performance_thresholds["memory_usage_percent"],
                },
            )

    def get_performance_summary(self, hours_back: int = 1) -> Dict[str, Any]:
        """
        Get performance summary for the last N hours.

        Args:
            hours_back: Number of hours to analyze

        Returns:
            Performance summary dictionary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        # API Performance
        recent_api_calls = [
            m
            for m in self.metrics["api_response_times"]
            if m["timestamp"] > cutoff_time
        ]

        api_summary = {}
        if recent_api_calls:
            response_times = [m["response_time_ms"] for m in recent_api_calls]
            api_summary = {
                "total_calls": len(recent_api_calls),
                "avg_response_time_ms": sum(response_times) / len(response_times),
                "max_response_time_ms": max(response_times),
                "min_response_time_ms": min(response_times),
                "error_rate": len(
                    [m for m in recent_api_calls if m["status_code"] >= 400]
                )
                / len(recent_api_calls),
            }

        # Database Performance
        recent_db_queries = [
            m
            for m in self.metrics["database_query_times"]
            if m["timestamp"] > cutoff_time
        ]

        db_summary = {}
        if recent_db_queries:
            query_times = [m["execution_time_ms"] for m in recent_db_queries]
            db_summary = {
                "total_queries": len(recent_db_queries),
                "avg_query_time_ms": sum(query_times) / len(query_times),
                "max_query_time_ms": max(query_times),
                "slow_queries": len(
                    [
                        q
                        for q in query_times
                        if q > self.performance_thresholds["db_query_time_ms"]
                    ]
                ),
            }

        # Cache Performance
        cache_stats = cache_manager.get_stats()

        # System Resources
        recent_resources = [
            m for m in self.metrics["system_resources"] if m["timestamp"] > cutoff_time
        ]

        resource_summary = {}
        if recent_resources:
            resource_summary = {
                "avg_cpu_percent": sum(m["cpu_percent"] for m in recent_resources)
                / len(recent_resources),
                "avg_memory_percent": sum(m["memory_percent"] for m in recent_resources)
                / len(recent_resources),
                "max_cpu_percent": max(m["cpu_percent"] for m in recent_resources),
                "max_memory_percent": max(
                    m["memory_percent"] for m in recent_resources
                ),
            }

        return {
            "time_period": f"Last {hours_back} hour(s)",
            "api_performance": api_summary,
            "database_performance": db_summary,
            "cache_performance": cache_stats,
            "system_resources": resource_summary,
            "active_alerts": len(self.alerts),
            "monitoring_enabled": self.monitoring_enabled,
        }

    def get_bottleneck_analysis(self) -> Dict[str, Any]:
        """
        Analyze performance data to identify bottlenecks.

        Returns:
            Analysis of performance bottlenecks and recommendations
        """
        analysis = {"bottlenecks": [], "recommendations": [], "overall_health": "good"}

        # Analyze API response times
        if self.metrics["api_response_times"]:
            recent_api_calls = list(self.metrics["api_response_times"])[
                -100:
            ]  # Last 100 calls
            avg_response_time = sum(
                m["response_time_ms"] for m in recent_api_calls
            ) / len(recent_api_calls)

            if avg_response_time > self.performance_thresholds["api_response_time_ms"]:
                analysis["bottlenecks"].append(
                    {
                        "type": "api_response_time",
                        "severity": "high" if avg_response_time > 1000 else "medium",
                        "description": f"Average API response time is {avg_response_time:.1f}ms",
                        "impact": "Poor user experience, potential user drop-off",
                    }
                )
                analysis["recommendations"].append(
                    "Consider implementing more aggressive caching"
                )
                analysis["recommendations"].append("Optimize database queries")
                analysis["overall_health"] = "needs_attention"

        # Analyze cache hit rate
        cache_stats = cache_manager.get_stats()
        if cache_stats["hit_rate"] < self.performance_thresholds["cache_hit_rate"]:
            analysis["bottlenecks"].append(
                {
                    "type": "cache_hit_rate",
                    "severity": "medium",
                    "description": f"Cache hit rate is {cache_stats['hit_rate']:.1%}",
                    "impact": "More database queries, slower response times",
                }
            )
            analysis["recommendations"].append("Review cache TTL settings")
            analysis["recommendations"].append(
                "Implement cache warming for popular data"
            )

        # Analyze database performance
        if self.metrics["database_query_times"]:
            recent_queries = list(self.metrics["database_query_times"])[-100:]
            slow_queries = [
                q
                for q in recent_queries
                if q["execution_time_ms"]
                > self.performance_thresholds["db_query_time_ms"]
            ]

            if (
                len(slow_queries) > len(recent_queries) * 0.1
            ):  # More than 10% slow queries
                analysis["bottlenecks"].append(
                    {
                        "type": "database_performance",
                        "severity": "high",
                        "description": f"{len(slow_queries)} slow queries in last 100 operations",
                        "impact": "High response times, potential timeout errors",
                    }
                )
                analysis["recommendations"].append(
                    "Add database indexes for slow queries"
                )
                analysis["recommendations"].append("Consider query optimization")
                analysis["overall_health"] = "critical"

        return analysis

    def _create_alert(self, alert_type: str, details: Dict[str, Any]):
        """Create performance alert."""
        alert = {
            "timestamp": datetime.utcnow(),
            "type": alert_type,
            "details": details,
            "resolved": False,
        }

        self.alerts.append(alert)

        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

    def get_alerts(self, unresolved_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get performance alerts.

        Args:
            unresolved_only: If True, return only unresolved alerts

        Returns:
            List of alert dictionaries
        """
        if unresolved_only:
            return [alert for alert in self.alerts if not alert["resolved"]]
        return self.alerts.copy()

    def resolve_alert(self, alert_index: int) -> bool:
        """
        Mark alert as resolved.

        Args:
            alert_index: Index of alert to resolve

        Returns:
            True if alert was resolved
        """
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index]["resolved"] = True
            return True
        return False


class PerformanceService(BaseService):
    """
    Service for performance monitoring and optimization.

    Provides high-level interface for performance tracking,
    analysis, and optimization recommendations.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.monitor = PerformanceMonitor()

        # Start background monitoring
        self._monitoring_task = None
        self.start_monitoring()

    def start_monitoring(self):
        """Start background performance monitoring."""
        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(self._background_monitoring())

    def stop_monitoring(self):
        """Stop background performance monitoring."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None

    async def _background_monitoring(self):
        """Background task for continuous system monitoring."""
        while True:
            try:
                # Track system resources every 30 seconds
                self.monitor.track_system_resources()
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in background monitoring: {e}")
                await asyncio.sleep(30)

    async def get_performance_dashboard(self) -> Dict[str, Any]:
        """
        Get comprehensive performance dashboard data.

        Returns:
            Dashboard data with performance metrics and insights
        """
        try:
            # Get performance summary
            summary = self.monitor.get_performance_summary(hours_back=1)

            # Get bottleneck analysis
            bottlenecks = self.monitor.get_bottleneck_analysis()

            # Get cache statistics with additional insights
            cache_stats = cache_manager.get_stats()
            cache_insights = self._analyze_cache_performance(cache_stats)

            # Get unresolved alerts
            alerts = self.monitor.get_alerts(unresolved_only=True)

            dashboard = {
                "overview": {
                    "status": bottlenecks["overall_health"],
                    "active_alerts": len(alerts),
                    "cache_hit_rate": cache_stats["hit_rate"],
                    "last_updated": datetime.utcnow().isoformat(),
                },
                "performance_summary": summary,
                "bottleneck_analysis": bottlenecks,
                "cache_insights": cache_insights,
                "alerts": alerts[:5],  # Show only top 5 alerts
                "recommendations": self._get_optimization_recommendations(
                    summary, bottlenecks
                ),
            }

            return dashboard

        except Exception as error:
            await self._handle_service_error(error, "get performance dashboard")

    async def optimize_performance(self) -> Dict[str, Any]:
        """
        Perform automated performance optimizations.

        Returns:
            Results of optimization actions taken
        """
        try:
            optimization_results = {
                "actions_taken": [],
                "recommendations": [],
                "estimated_improvement": {},
            }

            # Analyze current performance
            bottlenecks = self.monitor.get_bottleneck_analysis()

            # Perform cache optimizations
            if any(b["type"] == "cache_hit_rate" for b in bottlenecks["bottlenecks"]):
                # Trigger cache warming
                from app.core.cache import cache_warmer

                await cache_warmer.warm_trending_content()

                optimization_results["actions_taken"].append(
                    {
                        "action": "cache_warming",
                        "description": "Warmed trending content cache",
                        "expected_impact": "Improved cache hit rate for popular content",
                    }
                )

            # Database optimizations (would implement actual optimizations)
            if any(
                b["type"] == "database_performance" for b in bottlenecks["bottlenecks"]
            ):
                optimization_results["recommendations"].append(
                    {
                        "category": "database",
                        "action": "Add database indexes for frequently queried columns",
                        "priority": "high",
                        "estimated_improvement": "20-40% query performance improvement",
                    }
                )

            # System resource optimizations
            optimization_results["recommendations"].append(
                {
                    "category": "system",
                    "action": "Consider scaling horizontally if resource usage is consistently high",
                    "priority": "medium",
                    "estimated_improvement": "Better handling of concurrent requests",
                }
            )

            return optimization_results

        except Exception as error:
            await self._handle_service_error(error, "optimize performance")

    def _analyze_cache_performance(self, cache_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze cache performance and provide insights.

        Args:
            cache_stats: Cache statistics from cache manager

        Returns:
            Cache performance insights
        """
        insights = {
            "overall_rating": "excellent",
            "observations": [],
            "optimization_opportunities": [],
        }

        hit_rate = cache_stats.get("hit_rate", 0)

        if hit_rate >= 0.9:
            insights["overall_rating"] = "excellent"
            insights["observations"].append("Cache hit rate is excellent (>90%)")
        elif hit_rate >= 0.8:
            insights["overall_rating"] = "good"
            insights["observations"].append("Cache hit rate is good (80-90%)")
        elif hit_rate >= 0.6:
            insights["overall_rating"] = "fair"
            insights["observations"].append("Cache hit rate needs improvement (60-80%)")
            insights["optimization_opportunities"].append("Review cache TTL settings")
        else:
            insights["overall_rating"] = "poor"
            insights["observations"].append("Cache hit rate is poor (<60%)")
            insights["optimization_opportunities"].append(
                "Implement cache warming strategies"
            )
            insights["optimization_opportunities"].append("Review caching strategy")

        # Analyze cache operations
        total_ops = cache_stats.get("total_operations", 0)
        if total_ops > 1000:
            insights["observations"].append(
                f"High cache activity ({total_ops} operations)"
            )

        return insights

    def _get_optimization_recommendations(
        self, summary: Dict[str, Any], bottlenecks: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate optimization recommendations based on performance analysis.

        Args:
            summary: Performance summary
            bottlenecks: Bottleneck analysis

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        # API performance recommendations
        api_perf = summary.get("api_performance", {})
        if api_perf.get("avg_response_time_ms", 0) > 200:
            recommendations.append(
                {
                    "category": "api_performance",
                    "title": "Improve API Response Times",
                    "description": "Consider implementing response caching and optimizing database queries",
                    "priority": "high",
                    "estimated_impact": "30-50% improvement in response times",
                }
            )

        # Cache recommendations
        cache_perf = summary.get("cache_performance", {})
        if cache_perf.get("hit_rate", 1) < 0.8:
            recommendations.append(
                {
                    "category": "caching",
                    "title": "Optimize Cache Strategy",
                    "description": "Implement cache warming and review TTL settings",
                    "priority": "medium",
                    "estimated_impact": "20-30% reduction in database load",
                }
            )

        # Database recommendations
        db_perf = summary.get("database_performance", {})
        if db_perf.get("slow_queries", 0) > 0:
            recommendations.append(
                {
                    "category": "database",
                    "title": "Optimize Database Queries",
                    "description": "Add indexes for frequently queried columns and optimize slow queries",
                    "priority": "high",
                    "estimated_impact": "40-60% improvement in query performance",
                }
            )

        return recommendations


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def track_performance(operation_type: str):
    """
    Decorator for automatic performance tracking.

    Args:
        operation_type: Type of operation being tracked

    Usage:
        @track_performance("recommendation_generation")
        async def generate_recommendations(user_id):
            # Function implementation
            return recommendations
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Track performance based on operation type
                if operation_type == "recommendation_generation":
                    # Extract user_id and algorithm from args/kwargs
                    user_id = args[1] if len(args) > 1 else kwargs.get("user_id", 0)
                    algorithm = kwargs.get("algorithm", "unknown")
                    performance_monitor.track_recommendation_generation(
                        algorithm, user_id, execution_time
                    )
                elif operation_type == "database_query":
                    query_type = kwargs.get("query_type", "unknown")
                    performance_monitor.track_database_query(query_type, execution_time)

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                # Still track performance for failed operations
                if operation_type == "database_query":
                    query_type = kwargs.get("query_type", "unknown")
                    performance_monitor.track_database_query(query_type, execution_time)
                raise e

        return wrapper

    return decorator
