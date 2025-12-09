"""
Unit tests for Redis Cache Manager.
"""

import json
import pickle
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.cache import CacheInvalidator, CacheManager, CacheWarmer, cached


@pytest.mark.unit
@pytest.mark.cache
class TestCacheManager:
    """Test Redis cache manager functionality."""

    @pytest.fixture
    def cache_manager(self, mock_redis):
        """Create cache manager with mocked Redis."""
        cache = CacheManager()
        cache.redis_client = mock_redis
        return cache

    @pytest.mark.asyncio
    async def test_cache_set_get_cycle(self, cache_manager, mock_redis):
        """Test basic cache set/get operations."""
        # Test JSON serializable data
        test_data = {"user_id": 1, "recommendations": [1, 2, 3]}

        # Mock Redis responses
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=json.dumps(test_data).encode("utf-8"))

        # Test set
        result = await cache_manager.set("test_key", test_data, ttl=300)
        assert result is True
        mock_redis.setex.assert_called_once()

        # Test get
        cached_data = await cache_manager.get("test_key")
        assert cached_data == test_data
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_complex_object_serialization(self, cache_manager, mock_redis):
        """Test serialization of complex objects using pickle."""
        # Test complex object that can't be JSON serialized
        from datetime import datetime

        complex_data = {
            "timestamp": datetime.now(),
            "user_profile": {"name": "test"},
            "recommendations": [1, 2, 3],
        }

        # Mock Redis to simulate pickle serialization
        pickled_data = pickle.dumps(complex_data)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=pickled_data)

        # Test set/get cycle
        await cache_manager.set("complex_key", complex_data)
        result = await cache_manager.get("complex_key")

        # Should handle complex objects correctly
        assert result["user_profile"] == complex_data["user_profile"]
        assert result["recommendations"] == complex_data["recommendations"]

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_manager, mock_redis):
        """Test cache miss handling."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await cache_manager.get("nonexistent_key")

        assert result is None
        # Should increment miss counter
        assert cache_manager.cache_stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit_tracking(self, cache_manager, mock_redis):
        """Test cache hit/miss statistics tracking."""
        # Test cache hit
        mock_redis.get = AsyncMock(return_value=b'{"data": "value"}')
        await cache_manager.get("existing_key")

        # Test cache miss
        mock_redis.get = AsyncMock(return_value=None)
        await cache_manager.get("missing_key")

        stats = cache_manager.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["total_operations"] == 2

    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_manager, mock_redis):
        """Test cache deletion."""
        mock_redis.delete = AsyncMock(return_value=1)

        result = await cache_manager.delete("test_key")

        assert result is True
        mock_redis.delete.assert_called_once()
        assert cache_manager.cache_stats["deletes"] == 1

    @pytest.mark.asyncio
    async def test_cache_pattern_delete(self, cache_manager, mock_redis):
        """Test pattern-based cache deletion."""
        mock_redis.keys = AsyncMock(return_value=[b"user:1:rec", b"user:2:rec"])
        mock_redis.delete = AsyncMock(return_value=2)

        deleted_count = await cache_manager.delete_pattern("user:*:rec")

        assert deleted_count == 2
        mock_redis.keys.assert_called_once()
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_exists(self, cache_manager, mock_redis):
        """Test cache key existence check."""
        mock_redis.exists = AsyncMock(return_value=1)

        exists = await cache_manager.exists("test_key")

        assert exists is True
        mock_redis.exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_increment(self, cache_manager, mock_redis):
        """Test cache increment operations."""
        mock_redis.incrby = AsyncMock(return_value=5)

        result = await cache_manager.increment("counter_key", amount=3)

        assert result == 5
        mock_redis.incrby.assert_called_once_with(
            cache_manager._generate_key("counter_key", ""), 3
        )

    @pytest.mark.asyncio
    async def test_multi_get_operations(self, cache_manager, mock_redis):
        """Test batch get operations."""
        keys = ["key1", "key2", "key3"]
        mock_redis.mget = AsyncMock(
            return_value=[b'{"data": "value1"}', None, b'{"data": "value3"}']
        )

        results = await cache_manager.get_multi(keys)

        assert len(results) == 2  # Only keys with values
        assert results["key1"]["data"] == "value1"
        assert results["key3"]["data"] == "value3"
        assert "key2" not in results

    @pytest.mark.asyncio
    async def test_multi_set_operations(self, cache_manager, mock_redis):
        """Test batch set operations."""
        items = {"key1": {"data": "value1"}, "key2": {"data": "value2"}}

        mock_redis.mset = AsyncMock(return_value=True)
        mock_redis.pipeline = Mock(
            return_value=Mock(
                expire=Mock(), execute=AsyncMock(return_value=[True, True])
            )
        )

        result = await cache_manager.set_multi(items, ttl=300)

        assert result is True
        mock_redis.mset.assert_called_once()

    def test_key_generation(self, cache_manager):
        """Test cache key generation with namespaces."""
        # Test key without namespace
        key1 = cache_manager._generate_key("test_key")
        assert key1 == "smart_content:test_key"

        # Test key with namespace
        key2 = cache_manager._generate_key("test_key", "recommendations")
        assert key2 == "smart_content:recommendations:test_key"

    def test_cache_layer_ttl_configuration(self, cache_manager):
        """Test cache layer TTL configuration."""
        # Verify cache layers are properly configured
        assert "hot" in cache_manager.cache_layers
        assert "warm" in cache_manager.cache_layers
        assert "cold" in cache_manager.cache_layers
        assert "frozen" in cache_manager.cache_layers
        assert "permanent" in cache_manager.cache_layers

        # Verify TTL values make sense
        assert cache_manager.cache_layers["hot"] < cache_manager.cache_layers["warm"]
        assert cache_manager.cache_layers["warm"] < cache_manager.cache_layers["cold"]
        assert cache_manager.cache_layers["cold"] < cache_manager.cache_layers["frozen"]

    @pytest.mark.asyncio
    async def test_error_handling(self, cache_manager, mock_redis):
        """Test error handling in cache operations."""
        # Test Redis connection error
        mock_redis.get = AsyncMock(side_effect=Exception("Connection error"))

        result = await cache_manager.get("test_key")

        # Should handle errors gracefully
        assert result is None
        assert cache_manager.cache_stats["misses"] == 1


@pytest.mark.unit
@pytest.mark.cache
class TestCacheDecorator:
    """Test the @cached decorator functionality."""

    @pytest.mark.asyncio
    async def test_cached_decorator(self, mock_cache_manager):
        """Test the cached decorator caches function results."""
        call_count = 0

        @cached(ttl=300, namespace="test")
        async def expensive_function(param1, param2=None):
            nonlocal call_count
            call_count += 1
            return f"result_{param1}_{param2}"

        # Mock cache manager
        with patch("app.core.cache.cache_manager", mock_cache_manager):
            # First call - cache miss
            mock_cache_manager.get = AsyncMock(return_value=None)
            mock_cache_manager.set = AsyncMock(return_value=True)

            result1 = await expensive_function("test", param2="value")

            # Second call - cache hit
            mock_cache_manager.get = AsyncMock(return_value="result_test_value")

            result2 = await expensive_function("test", param2="value")

            # Function should only be called once
            assert call_count == 1
            assert result1 == "result_test_value"
            assert result2 == "result_test_value"


@pytest.mark.unit
@pytest.mark.cache
class TestCacheWarmer:
    """Test cache warming functionality."""

    @pytest.fixture
    def cache_warmer(self, mock_cache_manager):
        """Create cache warmer instance."""
        return CacheWarmer(mock_cache_manager)

    @pytest.mark.asyncio
    async def test_warm_trending_content(self, cache_warmer, mock_cache_manager):
        """Test warming trending content cache."""
        mock_cache_manager.exists = AsyncMock(return_value=False)
        mock_cache_manager.set = AsyncMock(return_value=True)

        await cache_warmer.warm_trending_content()

        # Should check existence and set cache for each trending type
        assert mock_cache_manager.exists.call_count == 4  # hot, rising, fresh, viral
        assert mock_cache_manager.set.call_count == 4

    @pytest.mark.asyncio
    async def test_warm_user_recommendations(self, cache_warmer, mock_cache_manager):
        """Test warming user recommendation cache."""
        user_ids = [1, 2, 3]

        mock_cache_manager.exists = AsyncMock(return_value=False)
        mock_cache_manager.set = AsyncMock(return_value=True)

        await cache_warmer.warm_user_recommendations(user_ids)

        # Should set cache for each user
        assert mock_cache_manager.set.call_count == len(user_ids)


@pytest.mark.unit
@pytest.mark.cache
class TestCacheInvalidator:
    """Test cache invalidation functionality."""

    @pytest.fixture
    def cache_invalidator(self, mock_cache_manager):
        """Create cache invalidator instance."""
        return CacheInvalidator(mock_cache_manager)

    @pytest.mark.asyncio
    async def test_user_update_invalidation(
        self, cache_invalidator, mock_cache_manager
    ):
        """Test cache invalidation on user update."""
        mock_cache_manager.delete = AsyncMock(return_value=True)
        mock_cache_manager.delete_pattern = AsyncMock(return_value=3)

        await cache_invalidator.invalidate_for_event("user_update", user_id=1)

        # Should invalidate user-related cache entries
        assert mock_cache_manager.delete.call_count > 0

    @pytest.mark.asyncio
    async def test_content_update_invalidation(
        self, cache_invalidator, mock_cache_manager
    ):
        """Test cache invalidation on content update."""
        mock_cache_manager.delete = AsyncMock(return_value=True)
        mock_cache_manager.delete_pattern = AsyncMock(return_value=5)

        await cache_invalidator.invalidate_for_event(
            "content_update", content_id=1, category_id=2
        )

        # Should invalidate content and trending caches
        assert mock_cache_manager.delete.call_count > 0
