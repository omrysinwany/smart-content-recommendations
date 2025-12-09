"""
Health check endpoint for the Smart Content Recommendations API.

This provides comprehensive health status for monitoring and deployment systems.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import redis.asyncio as redis
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_manager
from app.database import get_db

logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive health checking for all system components."""

    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and basic operations."""
        try:
            async for db in get_db():
                result = await db.execute(text("SELECT 1"))
                row = result.fetchone()
                if row and row[0] == 1:
                    return {
                        "status": "healthy",
                        "message": "Database connection successful",
                        "response_time_ms": 0,  # Could add timing
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": "Database query returned unexpected result",
                    }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}",
            }

    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and basic operations."""
        try:
            # Test basic Redis operations
            test_key = "health_check_test"
            test_value = "ok"

            await cache_manager.set(test_key, test_value, ttl=60)
            retrieved_value = await cache_manager.get(test_key)
            await cache_manager.delete(test_key)

            if retrieved_value == test_value:
                return {
                    "status": "healthy",
                    "message": "Redis connection and operations successful",
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "Redis operations failed - value mismatch",
                }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Redis connection failed: {str(e)}",
            }

    async def check_algorithms(self) -> Dict[str, Any]:
        """Check if recommendation algorithms are properly initialized."""
        try:
            from app.services.recommendation_service import RecommendationService

            # Initialize service to verify algorithm loading
            service = RecommendationService()

            # Check if algorithms are loaded
            if hasattr(service, "algorithms") and service.algorithms:
                algorithm_count = len(service.algorithms)
                algorithm_names = list(service.algorithms.keys())

                return {
                    "status": "healthy",
                    "message": f"All {algorithm_count} algorithms loaded successfully",
                    "algorithms": algorithm_names,
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "No recommendation algorithms loaded",
                }
        except Exception as e:
            logger.error(f"Algorithm health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Algorithm initialization failed: {str(e)}",
            }

    async def get_system_info(self) -> Dict[str, Any]:
        """Get basic system information."""
        import sys

        import psutil

        from app.config import get_settings

        settings = get_settings()

        return {
            "service_name": settings.PROJECT_NAME,
            "version": "1.0.0",
            "environment": getattr(settings, "ENVIRONMENT", "unknown"),
            "python_version": sys.version,
            "memory_usage_mb": round(
                psutil.Process().memory_info().rss / 1024 / 1024, 2
            ),
            "cpu_percent": psutil.cpu_percent(),
            "uptime": datetime.utcnow().isoformat(),
        }

    async def comprehensive_check(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        start_time = datetime.utcnow()

        # Run all checks concurrently
        db_check, redis_check, algo_check = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_algorithms(),
            return_exceptions=True,
        )

        # Handle any exceptions from gather
        if isinstance(db_check, Exception):
            db_check = {
                "status": "unhealthy",
                "message": f"Database check failed: {str(db_check)}",
            }
        if isinstance(redis_check, Exception):
            redis_check = {
                "status": "unhealthy",
                "message": f"Redis check failed: {str(redis_check)}",
            }
        if isinstance(algo_check, Exception):
            algo_check = {
                "status": "unhealthy",
                "message": f"Algorithm check failed: {str(algo_check)}",
            }

        # Determine overall status
        all_healthy = all(
            check["status"] == "healthy"
            for check in [db_check, redis_check, algo_check]
        )

        overall_status = "healthy" if all_healthy else "unhealthy"

        end_time = datetime.utcnow()
        check_duration = (end_time - start_time).total_seconds()

        return {
            "status": overall_status,
            "timestamp": end_time.isoformat(),
            "check_duration_seconds": round(check_duration, 3),
            "components": {
                "database": db_check,
                "redis": redis_check,
                "algorithms": algo_check,
            },
            "system_info": await self.get_system_info(),
        }


# Global health checker instance
health_checker = HealthChecker()


async def quick_health_check() -> Dict[str, str]:
    """Quick health check for basic liveness probe."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Smart Content Recommendations",
    }


async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check for readiness probe."""
    return await health_checker.comprehensive_check()
