"""
Unit tests for Recommendation Service.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from app.algorithms.base import RecommendationResult
from app.core.exceptions import NotFoundError, ValidationError
from app.services.recommendation_service import RecommendationService


@pytest.mark.unit
class TestRecommendationService:
    """Test recommendation service business logic."""

    @pytest.fixture
    def service(self, mock_db):
        """Create recommendation service instance."""
        return RecommendationService(mock_db)

    @pytest.mark.asyncio
    async def test_algorithm_selection_logic(self, service):
        """Test intelligent algorithm selection based on user profile."""
        # Test cases for different user types
        test_cases = [
            # New user with minimal interactions
            {
                "user_data": {"total_interactions": 2},
                "expected_algorithm_type": "trending",
            },
            # Growing user with some interactions
            {
                "user_data": {"total_interactions": 15},
                "expected_algorithm_type": "hybrid",
            },
            # Experienced user with many interactions
            {
                "user_data": {"total_interactions": 75},
                "expected_algorithm_type": "hybrid",
            },
        ]

        for case in test_cases:
            # Mock user data
            service.interaction_repo.get_user_recommendation_data = AsyncMock(
                return_value=case["user_data"]
            )

            # Test algorithm selection
            algorithm = await service._select_algorithm(user_id=1, algorithm="auto")

            # Verify correct algorithm type is selected
            algorithm_name = algorithm.name.lower()
            if case["expected_algorithm_type"] == "trending":
                assert "trending" in algorithm_name or "ab_test" in algorithm_name
            elif case["expected_algorithm_type"] == "hybrid":
                assert "hybrid" in algorithm_name or "ab_test" in algorithm_name

    @pytest.mark.asyncio
    async def test_recommendation_validation(self, service):
        """Test request validation logic."""
        # Mock user repository
        from app.models.user import User

        valid_user = User(
            id=1,
            email="test@example.com",
            hashed_password="mock_hashed_password",
            full_name="Test User",
            is_active=True,
        )
        service.user_repo.get = AsyncMock(return_value=valid_user)

        # Test valid request
        await service._validate_recommendation_request(
            user_id=1, algorithm="hybrid", num_recommendations=10
        )  # Should not raise

        # Test invalid user
        service.user_repo.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service._validate_recommendation_request(
                user_id=999, algorithm="hybrid", num_recommendations=10
            )

        # Test invalid algorithm
        service.user_repo.get = AsyncMock(return_value=valid_user)
        with pytest.raises(ValidationError):
            await service._validate_recommendation_request(
                user_id=1, algorithm="invalid_algorithm", num_recommendations=10
            )

        # Test invalid num_recommendations
        with pytest.raises(ValidationError):
            await service._validate_recommendation_request(
                user_id=1, algorithm="hybrid", num_recommendations=0
            )

        with pytest.raises(ValidationError):
            await service._validate_recommendation_request(
                user_id=1, algorithm="hybrid", num_recommendations=100  # Exceeds max
            )

    @pytest.mark.asyncio
    async def test_recommendation_enrichment(self, service):
        """Test recommendation enrichment with content details."""
        # Mock recommendation result
        recommendation_result = RecommendationResult(
            content_ids=[1, 2, 3],
            scores=[0.95, 0.87, 0.82],
            algorithm_name="Test Algorithm",
            user_id=1,
            metadata={"test": True},
        )

        # Mock content details
        content_details = [
            {
                "content": {
                    "title": "Python Tutorial",
                    "description": "Learn Python programming",
                    "content_type": "article",
                    "category": {"name": "Programming"},
                    "author": "Test Author",
                    "image_url": "https://example.com/image.jpg",
                    "created_at": "2025-01-01T00:00:00Z",
                },
                "stats": {"views": 1000, "likes": 50, "saves": 10},
            },
            {
                "content": {
                    "title": "Web Development",
                    "description": "Build web applications",
                    "content_type": "course",
                    "category": {"name": "Web Dev"},
                    "author": "Test Author 2",
                    "image_url": "https://example.com/image2.jpg",
                    "created_at": "2025-01-02T00:00:00Z",
                },
                "stats": {"views": 800, "likes": 40, "saves": 15},
            },
            {
                "content": {
                    "title": "Data Science",
                    "description": "Analyze data effectively",
                    "content_type": "video",
                    "category": {"name": "Data"},
                    "author": "Test Author 3",
                    "image_url": "https://example.com/image3.jpg",
                    "created_at": "2025-01-03T00:00:00Z",
                },
                "stats": {"views": 1200, "likes": 80, "saves": 25},
            },
        ]

        # Mock repository calls
        service.content_repo.get_content_with_stats = AsyncMock(
            side_effect=content_details
        )
        service.interaction_repo.get_user_content_interactions = AsyncMock(
            return_value={"has_liked": False, "has_saved": True}
        )

        # Test enrichment
        enriched = await service._enrich_recommendations(
            recommendation_result, user_id=1
        )

        # Verify enrichment structure
        assert "recommendations" in enriched
        assert "algorithm" in enriched
        assert "user_id" in enriched
        assert "generated_at" in enriched
        assert "total_items" in enriched

        # Verify recommendation items
        recommendations = enriched["recommendations"]
        assert len(recommendations) == 3

        # Check first recommendation
        first_rec = recommendations[0]
        assert first_rec["content_id"] == 1
        assert first_rec["title"] == "Python Tutorial"
        assert first_rec["recommendation_score"] == 0.95
        assert "user_context" in first_rec
        assert first_rec["stats"]["views"] == 1000

    @pytest.mark.asyncio
    async def test_trending_recommendations(self, service):
        """Test trending content recommendations."""
        # Mock trending algorithm
        mock_trending_result = RecommendationResult(
            content_ids=[10, 11, 12],
            scores=[1.0, 0.95, 0.90],
            algorithm_name="Trending (Hot)",
            user_id=0,  # Trending is not user-specific
            metadata={"trending_type": "hot"},
        )

        service.algorithms["trending_hot"].generate_recommendations = AsyncMock(
            return_value=mock_trending_result
        )

        # Mock content enrichment
        service._enrich_recommendations = AsyncMock(
            return_value={
                "recommendations": [
                    {"content_id": 10, "title": "Trending Article 1"},
                    {"content_id": 11, "title": "Trending Article 2"},
                    {"content_id": 12, "title": "Trending Article 3"},
                ],
                "algorithm": "Trending (Hot)",
                "total_items": 3,
            }
        )

        # Test trending recommendations
        result = await service.get_trending_recommendations(
            trending_type="hot", num_recommendations=3
        )

        # Verify result
        assert result["algorithm"] == "Trending (Hot)"
        assert len(result["recommendations"]) == 3
        assert result["total_items"] == 3

    @pytest.mark.asyncio
    async def test_similar_content_recommendations(self, service):
        """Test similar content recommendations."""
        # Mock content existence check
        service.content_repo.get_content_with_stats = AsyncMock(
            return_value={
                "content": {"id": 1, "title": "Reference Content"},
                "stats": {"views": 500},
            }
        )

        # Mock similar content algorithm
        mock_similar_result = RecommendationResult(
            content_ids=[2, 3, 4],
            scores=[0.85, 0.80, 0.75],
            algorithm_name="Content Similarity",
            user_id=1,
            metadata={"reference_content_id": 1},
        )

        service.algorithms["content_based"].generate_recommendations = AsyncMock(
            return_value=mock_similar_result
        )

        # Mock enrichment
        service._enrich_recommendations = AsyncMock(
            return_value={
                "recommendations": [
                    {"content_id": 2, "title": "Similar Content 1"},
                    {"content_id": 3, "title": "Similar Content 2"},
                    {"content_id": 4, "title": "Similar Content 3"},
                ],
                "algorithm": "Content Similarity",
                "total_items": 3,
            }
        )

        # Test similar content
        result = await service.get_similar_content(
            content_id=1, num_recommendations=3, user_id=1
        )

        # Verify result
        assert result["algorithm"] == "Content Similarity"
        assert len(result["recommendations"]) == 3

    @pytest.mark.asyncio
    async def test_recommendation_feedback_processing(self, service):
        """Test user feedback processing."""
        # Test valid feedback types
        valid_feedback_types = [
            "clicked",
            "liked",
            "dismissed",
            "not_interested",
            "reported",
        ]

        for feedback_type in valid_feedback_types:
            # Mock interaction creation
            service.interaction_repo.create_or_update_interaction = AsyncMock()

            result = await service.record_recommendation_feedback(
                user_id=1,
                content_id=1,
                feedback_type=feedback_type,
                algorithm="hybrid",
                recommendation_id="test_rec_123",
            )

            # Verify feedback processing
            assert result["success"] is True
            assert feedback_type in result["message"]
            assert result["feedback_data"]["feedback_type"] == feedback_type

        # Test invalid feedback type
        with pytest.raises(ValidationError):
            await service.record_recommendation_feedback(
                user_id=1,
                content_id=1,
                feedback_type="invalid_feedback",
                algorithm="hybrid",
            )

    @pytest.mark.asyncio
    async def test_recommendation_explanation(self, service):
        """Test recommendation explanation generation."""
        # Mock algorithm selection
        mock_algorithm = Mock()
        mock_algorithm.explain_recommendation = AsyncMock(
            return_value={
                "algorithm": "hybrid",
                "confidence": 0.85,
                "reasons": ["Based on your interests in Python and AI"],
            }
        )
        service._select_algorithm = AsyncMock(return_value=mock_algorithm)

        # Mock content and user data
        service.content_repo.get_content_with_stats = AsyncMock(
            return_value={
                "content": {
                    "title": "Advanced Python Patterns",
                    "content_type": "article",
                    "category": {"name": "Programming"},
                },
                "stats": {"views": 1000, "likes": 75},
            }
        )

        service.interaction_repo.get_user_recommendation_data = AsyncMock(
            return_value={
                "total_interactions": 25,
                "preferred_content_types": ["article", "video"],
            }
        )

        # Test explanation
        explanation = await service.explain_recommendation(
            user_id=1, content_id=1, algorithm="auto"
        )

        # Verify explanation structure
        assert "content_details" in explanation
        assert "user_context" in explanation
        assert explanation["content_details"]["title"] == "Advanced Python Patterns"
        assert explanation["user_context"]["total_interactions"] == 25

    @pytest.mark.asyncio
    async def test_performance_analytics(self, service):
        """Test recommendation performance analytics."""
        result = await service.get_recommendation_performance(
            algorithm="hybrid", days_back=7
        )

        # Verify analytics structure
        assert "time_period" in result
        assert "algorithms" in result
        assert "overall" in result

        # Verify time period
        assert result["time_period"]["days"] == 7

        # Verify algorithm metrics
        if "hybrid" in result["algorithms"]:
            hybrid_metrics = result["algorithms"]["hybrid"]
            assert "recommendations_generated" in hybrid_metrics
            assert "click_through_rate" in hybrid_metrics
            assert "avg_relevance_score" in hybrid_metrics

        # Verify overall metrics
        overall = result["overall"]
        assert "total_users_served" in overall
        assert "avg_recommendations_per_user" in overall
        assert "system_response_time_ms" in overall

    @pytest.mark.asyncio
    async def test_error_handling(self, service):
        """Test error handling in recommendation service."""
        # Mock algorithm failure
        service.algorithms["hybrid"].generate_recommendations = AsyncMock(
            side_effect=Exception("Algorithm failure")
        )

        # Mock validation to pass
        service._validate_recommendation_request = AsyncMock()
        service._select_algorithm = AsyncMock(return_value=service.algorithms["hybrid"])

        # Should handle errors gracefully
        with pytest.raises(
            Exception
        ):  # Service should re-raise for proper error handling
            await service.get_user_recommendations(user_id=1, num_recommendations=5)

    @pytest.mark.asyncio
    async def test_caching_integration(self, service):
        """Test cache integration in recommendation service."""
        # The service methods should have @cached decorators
        # This test verifies the decorators are properly applied

        # Check if methods have cache-related attributes
        assert hasattr(service.get_user_recommendations, "__wrapped__")
        assert hasattr(service.get_trending_recommendations, "__wrapped__")

        # Verify cache keys are generated correctly by calling the methods
        # Mock all dependencies
        service._validate_recommendation_request = AsyncMock()
        service._select_algorithm = AsyncMock(
            return_value=Mock(
                generate_recommendations=AsyncMock(
                    return_value=RecommendationResult(
                        content_ids=[1, 2],
                        scores=[0.9, 0.8],
                        algorithm_name="test",
                        user_id=1,
                    )
                )
            )
        )
        service._enrich_recommendations = AsyncMock(
            return_value={"recommendations": [], "algorithm": "test", "total_items": 0}
        )
        service._log_recommendation_event = AsyncMock()

        # Call cached method
        result = await service.get_user_recommendations(
            user_id=1, num_recommendations=5
        )

        # Should return valid result structure
        assert "recommendations" in result
        assert "algorithm" in result
