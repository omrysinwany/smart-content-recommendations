"""
Redis caching layer for high-performance data access.

This provides:
1. Multi-level caching strategy
2. Cache invalidation patterns
3. Distributed caching for scalability
4. Performance monitoring and analytics
5. Cache warming and precomputation
"""

import asyncio
import hashlib
import json
import logging
import pickle
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Advanced Redis cache manager with multiple caching strategies.

    Features:
    - Multi-level TTL management
    - Automatic serialization/deserialization
    - Cache invalidation patterns
    - Performance monitoring
    - Batch operations for efficiency
    """

    def __init__(self):
        """Initialize Redis connection and cache configuration."""
        self.redis_client = None
        self._connection_pool = None

        # Cache configuration
        self.default_ttl = settings.redis_cache_ttl
        self.key_prefix = "smart_content:"

        # Performance tracking
        self.cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

        # Cache layers with different TTLs
        self.cache_layers = {
            "hot": 300,  # 5 minutes - frequently accessed data
            "warm": 1800,  # 30 minutes - moderately accessed data
            "cold": 3600,  # 1 hour - rarely accessed data
            "frozen": 86400,  # 24 hours - static/computed data
            "permanent": 604800,  # 1 week - rarely changing data
        }

    async def connect(self):
        """Establish Redis connection optimized for AWS ElastiCache."""
        try:
            # AWS ElastiCache optimized connection parameters
            connection_kwargs = {
                "max_connections": 20,
                "retry_on_timeout": True,
                "decode_responses": False,  # We'll handle encoding ourselves
                "socket_keepalive": True,
                "socket_keepalive_options": {},
            }

            # Add SSL support for ElastiCache with encryption in transit
            if settings.redis_ssl or settings.is_aws_environment:
                connection_kwargs["ssl"] = settings.redis_ssl
                connection_kwargs["ssl_cert_reqs"] = (
                    None  # Don't require certificates for ElastiCache
                )

            # AWS ElastiCache specific optimizations
            if settings.is_aws_environment:
                connection_kwargs.update(
                    {
                        "socket_connect_timeout": 10,
                        "socket_timeout": 30,
                        "health_check_interval": 30,
                    }
                )

            self._connection_pool = redis.ConnectionPool.from_url(
                settings.redis_url, **connection_kwargs
            )

            self.redis_client = redis.Redis(connection_pool=self._connection_pool)

            # Test connection
            await self.redis_client.ping()
            logger.info(
                f"Redis connection established successfully (AWS: {settings.is_aws_environment})"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            if settings.is_aws_environment:
                logger.error(
                    "Note: Ensure ElastiCache cluster is accessible from your ECS/EKS service"
                )
            raise ConnectionError(f"Redis connection failed: {e}")

    async def disconnect(self):
        """Clean up Redis connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self._connection_pool:
            await self._connection_pool.disconnect()

    def _generate_key(self, key: str, namespace: str = "") -> str:
        """
        Generate standardized cache key.

        Args:
            key: Base key
            namespace: Optional namespace for key organization

        Returns:
            Formatted cache key
        """
        if namespace:
            return f"{self.key_prefix}{namespace}:{key}"
        return f"{self.key_prefix}{key}"

    def _serialize_value(self, value: Any) -> bytes:
        """
        Serialize value for Redis storage.

        Uses pickle for complex objects, JSON for simple ones.
        """
        try:
            # Try JSON first (faster and more readable)
            if isinstance(value, (dict, list, str, int, float, bool)):
                return json.dumps(value).encode("utf-8")
            else:
                # Use pickle for complex objects
                return pickle.dumps(value)
        except Exception as e:
            logger.warning(f"Serialization fallback to pickle: {e}")
            return pickle.dumps(value)

    def _deserialize_value(self, value: bytes) -> Any:
        """
        Deserialize value from Redis.

        Attempts JSON first, falls back to pickle.
        """
        try:
            # Try JSON first
            return json.loads(value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                # Fall back to pickle
                return pickle.loads(value)
            except Exception as e:
                logger.error(f"Failed to deserialize cache value: {e}")
                return None

    async def get(self, key: str, namespace: str = "") -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace

        Returns:
            Cached value or None if not found
        """
        if not self.redis_client:
            return None

        try:
            cache_key = self._generate_key(key, namespace)
            value = await self.redis_client.get(cache_key)

            if value is not None:
                self.cache_stats["hits"] += 1
                return self._deserialize_value(value)
            else:
                self.cache_stats["misses"] += 1
                return None

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.cache_stats["misses"] += 1
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "",
        cache_layer: str = "warm",
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (overrides cache_layer)
            namespace: Optional namespace
            cache_layer: Cache layer determining TTL

        Returns:
            True if successfully set
        """
        if not self.redis_client:
            return False

        try:
            cache_key = self._generate_key(key, namespace)
            serialized_value = self._serialize_value(value)

            # Determine TTL
            if ttl is None:
                ttl = self.cache_layers.get(cache_layer, self.default_ttl)

            # Set with expiration
            await self.redis_client.setex(cache_key, ttl, serialized_value)
            self.cache_stats["sets"] += 1
            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str, namespace: str = "") -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete
            namespace: Optional namespace

        Returns:
            True if key was deleted
        """
        if not self.redis_client:
            return False

        try:
            cache_key = self._generate_key(key, namespace)
            result = await self.redis_client.delete(cache_key)
            if result > 0:
                self.cache_stats["deletes"] += 1
            return result > 0

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str, namespace: str = "") -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Key pattern (supports wildcards)
            namespace: Optional namespace

        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0

        try:
            search_pattern = self._generate_key(pattern, namespace)
            keys = await self.redis_client.keys(search_pattern)

            if keys:
                deleted = await self.redis_client.delete(*keys)
                self.cache_stats["deletes"] += deleted
                return deleted
            return 0

        except Exception as e:
            logger.error(f"Cache pattern delete error for pattern {pattern}: {e}")
            return 0

    async def exists(self, key: str, namespace: str = "") -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key
            namespace: Optional namespace

        Returns:
            True if key exists
        """
        if not self.redis_client:
            return False

        try:
            cache_key = self._generate_key(key, namespace)
            return await self.redis_client.exists(cache_key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def increment(
        self, key: str, amount: int = 1, namespace: str = ""
    ) -> Optional[int]:
        """
        Increment a numeric value in cache.

        Args:
            key: Cache key
            amount: Amount to increment
            namespace: Optional namespace

        Returns:
            New value after increment
        """
        if not self.redis_client:
            return None

        try:
            cache_key = self._generate_key(key, namespace)
            return await self.redis_client.incrby(cache_key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None

    async def get_multi(self, keys: List[str], namespace: str = "") -> Dict[str, Any]:
        """
        Get multiple values from cache in one operation.

        Args:
            keys: List of cache keys
            namespace: Optional namespace

        Returns:
            Dictionary mapping keys to values
        """
        if not self.redis_client or not keys:
            return {}

        try:
            cache_keys = [self._generate_key(key, namespace) for key in keys]
            values = await self.redis_client.mget(cache_keys)

            result = {}
            for i, (original_key, value) in enumerate(zip(keys, values)):
                if value is not None:
                    result[original_key] = self._deserialize_value(value)
                    self.cache_stats["hits"] += 1
                else:
                    self.cache_stats["misses"] += 1

            return result

        except Exception as e:
            logger.error(f"Cache multi-get error: {e}")
            self.cache_stats["misses"] += len(keys)
            return {}

    async def set_multi(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
        namespace: str = "",
        cache_layer: str = "warm",
    ) -> bool:
        """
        Set multiple key-value pairs in one operation.

        Args:
            items: Dictionary of key-value pairs
            ttl: Time to live in seconds
            namespace: Optional namespace
            cache_layer: Cache layer for TTL

        Returns:
            True if all items were set successfully
        """
        if not self.redis_client or not items:
            return False

        try:
            # Prepare data for mset
            cache_data = {}
            for key, value in items.items():
                cache_key = self._generate_key(key, namespace)
                cache_data[cache_key] = self._serialize_value(value)

            # Set all values
            await self.redis_client.mset(cache_data)

            # Set TTL for each key if specified
            if ttl or cache_layer != "warm":
                ttl_value = ttl or self.cache_layers.get(cache_layer, self.default_ttl)

                # Use pipeline for efficiency
                pipe = self.redis_client.pipeline()
                for cache_key in cache_data.keys():
                    pipe.expire(cache_key, ttl_value)
                await pipe.execute()

            self.cache_stats["sets"] += len(items)
            return True

        except Exception as e:
            logger.error(f"Cache multi-set error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_operations = sum(self.cache_stats.values())
        hit_rate = (
            self.cache_stats["hits"]
            / (self.cache_stats["hits"] + self.cache_stats["misses"])
            if (self.cache_stats["hits"] + self.cache_stats["misses"]) > 0
            else 0
        )

        return {
            **self.cache_stats,
            "total_operations": total_operations,
            "hit_rate": round(hit_rate, 4),
            "miss_rate": round(1 - hit_rate, 4),
        }

    async def clear_stats(self):
        """Reset cache statistics."""
        self.cache_stats = {key: 0 for key in self.cache_stats}


# Global cache manager instance
cache_manager = CacheManager()


def cached(
    key_func: Optional[Callable] = None,
    ttl: int = 1800,
    namespace: str = "",
    cache_layer: str = "warm",
    invalidate_on: Optional[List[str]] = None,
):
    """
    Decorator for caching function results.

    Args:
        key_func: Function to generate cache key from arguments
        ttl: Time to live in seconds
        namespace: Cache namespace
        cache_layer: Cache layer for TTL management
        invalidate_on: List of events that should invalidate this cache

    Usage:
        @cached(ttl=300, namespace="user_recs")
        async def get_user_recommendations(user_id: int):
            # Expensive computation
            return recommendations
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Try to get from cache
            cached_result = await cache_manager.get(cache_key, namespace)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(
                cache_key, result, ttl=ttl, namespace=namespace, cache_layer=cache_layer
            )

            return result

        # Add cache invalidation method
        wrapper.invalidate = lambda *args, **kwargs: cache_manager.delete(
            key_func(*args, **kwargs) if key_func else func.__name__, namespace
        )

        return wrapper

    return decorator


class CacheWarmer:
    """
    Cache warming system for precomputing expensive operations.

    This proactively computes and caches expensive data before it's needed,
    improving user experience by eliminating cache misses for common requests.
    """

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.warming_tasks = {}

    async def warm_user_recommendations(self, user_ids: List[int]):
        """
        Warm cache with user recommendations.

        Args:
            user_ids: List of user IDs to warm cache for
        """
        logger.info(f"Warming recommendation cache for {len(user_ids)} users")

        # This would typically call the recommendation service
        # For demo purposes, we'll simulate the warming process
        for user_id in user_ids:
            cache_key = f"user_recommendations:{user_id}"

            # Check if already cached
            if not await self.cache.exists(cache_key, "recommendations"):
                # Simulate expensive recommendation computation
                mock_recommendations = {
                    "user_id": user_id,
                    "recommendations": [
                        {"content_id": i, "score": 0.9 - i * 0.1} for i in range(10)
                    ],
                    "generated_at": datetime.utcnow().isoformat(),
                    "algorithm": "cache_warmer",
                }

                await self.cache.set(
                    cache_key,
                    mock_recommendations,
                    namespace="recommendations",
                    cache_layer="warm",
                )

    async def warm_trending_content(self):
        """Warm cache with trending content for different time periods."""
        trending_types = ["hot", "rising", "fresh", "viral"]

        for trending_type in trending_types:
            cache_key = f"trending:{trending_type}"

            if not await self.cache.exists(cache_key, "trending"):
                # Simulate trending computation
                mock_trending = {
                    "trending_type": trending_type,
                    "content": [
                        {"content_id": i, "trending_score": 100 - i * 5}
                        for i in range(20)
                    ],
                    "generated_at": datetime.utcnow().isoformat(),
                }

                await self.cache.set(
                    cache_key,
                    mock_trending,
                    namespace="trending",
                    cache_layer="hot",  # Trending data changes quickly
                )

    async def warm_content_similarities(self, content_ids: List[int]):
        """
        Warm cache with content similarity data.

        Args:
            content_ids: List of content IDs to compute similarities for
        """
        logger.info(f"Warming similarity cache for {len(content_ids)} content items")

        for content_id in content_ids:
            cache_key = f"similar_content:{content_id}"

            if not await self.cache.exists(cache_key, "similarities"):
                # Simulate similarity computation
                mock_similar = {
                    "content_id": content_id,
                    "similar_content": [
                        {"content_id": content_id + i, "similarity": 0.8 - i * 0.1}
                        for i in range(1, 11)
                    ],
                    "computed_at": datetime.utcnow().isoformat(),
                }

                await self.cache.set(
                    cache_key,
                    mock_similar,
                    namespace="similarities",
                    cache_layer="frozen",  # Similarities change slowly
                )

    async def schedule_warming(self):
        """
        Schedule regular cache warming tasks.

        This would typically be called by a background job scheduler.
        """
        warming_tasks = [
            self.warm_trending_content(),
            # self.warm_user_recommendations(active_user_ids),  # Would get from DB
            # self.warm_content_similarities(popular_content_ids)  # Would get from DB
        ]

        await asyncio.gather(*warming_tasks, return_exceptions=True)
        logger.info("Cache warming cycle completed")


class CacheInvalidator:
    """
    Intelligent cache invalidation system.

    Automatically invalidates related cache entries when data changes,
    ensuring cache consistency without over-invalidation.
    """

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

        # Define invalidation patterns
        self.invalidation_patterns = {
            "user_update": [
                "user_recommendations:{user_id}",
                "user_profile:{user_id}",
                "user_similarities:*",  # Wildcard pattern
            ],
            "content_update": [
                "content_detail:{content_id}",
                "similar_content:{content_id}",
                "trending:*",  # Content updates may affect trending
                "category_content:{category_id}",
            ],
            "interaction_create": [
                "user_recommendations:{user_id}",
                "content_stats:{content_id}",
                "trending:*",
                "similar_users:{user_id}",
            ],
        }

    async def invalidate_for_event(self, event_type: str, **event_data):
        """
        Invalidate cache entries based on data change events.

        Args:
            event_type: Type of event (user_update, content_update, etc.)
            **event_data: Event-specific data for key generation
        """
        patterns = self.invalidation_patterns.get(event_type, [])

        invalidation_tasks = []
        for pattern in patterns:
            try:
                # Format pattern with event data
                formatted_pattern = pattern.format(**event_data)

                if "*" in formatted_pattern:
                    # Handle wildcard patterns
                    invalidation_tasks.append(
                        self._invalidate_pattern(formatted_pattern)
                    )
                else:
                    # Handle specific keys
                    invalidation_tasks.append(self.cache.delete(formatted_pattern))

            except KeyError as e:
                logger.warning(f"Missing event data for pattern {pattern}: {e}")

        # Execute all invalidations concurrently
        if invalidation_tasks:
            await asyncio.gather(*invalidation_tasks, return_exceptions=True)
            logger.info(f"Cache invalidation completed for event: {event_type}")

    async def _invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching a pattern."""
        deleted_count = await self.cache.delete_pattern(pattern)
        if deleted_count > 0:
            logger.info(
                f"Invalidated {deleted_count} cache entries for pattern: {pattern}"
            )


# Initialize global instances
cache_warmer = CacheWarmer(cache_manager)
cache_invalidator = CacheInvalidator(cache_manager)


async def init_cache():
    """Initialize cache connection and warming."""
    await cache_manager.connect()

    # Start initial cache warming
    await cache_warmer.warm_trending_content()

    logger.info("Cache system initialized successfully")


async def cleanup_cache():
    """Cleanup cache connections."""
    await cache_manager.disconnect()
    logger.info("Cache system cleaned up")
