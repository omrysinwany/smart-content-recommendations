"""
Unit tests for Hybrid Recommendation Algorithm.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from app.algorithms.base import RecommendationResult
from app.algorithms.hybrid import ABTestingHybridRecommendation, HybridRecommendation


@pytest.mark.unit
@pytest.mark.algorithms
class TestHybridRecommendation:
    """Test hybrid recommendation algorithm."""

    @pytest.fixture
    def algorithm(self, mock_db):
        """Create hybrid algorithm instance."""
        return HybridRecommendation(mock_db)

    @pytest.mark.asyncio
    async def test_user_profile_analysis(self, algorithm):
        """Test user profile analysis for algorithm weight determination."""
        # Mock user data for different user types
        test_cases = [
            # New user
            {"input": {"total_interactions": 2}, "expected_level": "minimal"},
            # Active user
            {"input": {"total_interactions": 15}, "expected_level": "low"},
            # Power user
            {"input": {"total_interactions": 75}, "expected_level": "high"},
        ]

        for case in test_cases:
            algorithm.interaction_repo.get_user_recommendation_data = AsyncMock(
                return_value=case["input"]
            )

            profile = await algorithm._analyze_user_profile(user_id=1)

            assert profile["personalization_level"] == case["expected_level"]
            assert profile["total_interactions"] == case["input"]["total_interactions"]

    def test_dynamic_weight_calculation(self, algorithm):
        """Test dynamic weight calculation based on user profile."""
        test_profiles = [
            # New user - should prefer trending
            {
                "profile": {
                    "personalization_level": "minimal",
                    "is_new_user": True,
                    "total_interactions": 2,
                },
                "expected_trending_weight": 0.5,  # Should be high
            },
            # Experienced user - should prefer personalization
            {
                "profile": {
                    "personalization_level": "high",
                    "is_new_user": False,
                    "total_interactions": 100,
                },
                "expected_content_weight": 0.5,  # Should be high
            },
        ]

        for case in test_profiles:
            weights = algorithm._calculate_dynamic_weights(case["profile"])

            # Verify weights sum to 1
            assert abs(sum(weights.values()) - 1.0) < 0.01

            # Verify all weights are positive
            assert all(w >= 0 for w in weights.values())

            # Verify expected weight patterns
            if "expected_trending_weight" in case:
                assert weights["trending"] >= case["expected_trending_weight"]
            if "expected_content_weight" in case:
                assert weights["content_based"] >= case["expected_content_weight"]

    @pytest.mark.asyncio
    async def test_algorithm_combination(self, algorithm):
        """Test combination of multiple algorithm results."""
        # Mock algorithm results
        mock_results = {
            "content_based": RecommendationResult(
                content_ids=[1, 2, 3],
                scores=[0.9, 0.8, 0.7],
                algorithm_name="content_based",
                user_id=1,
            ),
            "collaborative": RecommendationResult(
                content_ids=[2, 3, 4],
                scores=[0.85, 0.75, 0.65],
                algorithm_name="collaborative",
                user_id=1,
            ),
            "trending": RecommendationResult(
                content_ids=[3, 4, 5],
                scores=[0.95, 0.85, 0.75],
                algorithm_name="trending",
                user_id=1,
            ),
        }

        algorithm._get_algorithm_recommendations = AsyncMock(return_value=mock_results)

        # Test weights
        weights = {"content_based": 0.4, "collaborative": 0.3, "trending": 0.3}

        combined = algorithm._combine_algorithm_results(mock_results, weights)

        # Verify combination
        assert len(combined) > 0

        # Content that appears in multiple algorithms should get bonus
        content_3_score = next(
            score for content_id, score in combined if content_id == 3
        )
        content_1_score = next(
            score for content_id, score in combined if content_id == 1
        )

        # Content 3 appears in all algorithms, should have higher combined score
        assert content_3_score > content_1_score

    @pytest.mark.asyncio
    async def test_diversity_optimization(self, algorithm):
        """Test diversity optimization to avoid filter bubbles."""
        # Mock recommendations with low diversity (all same category)
        recommendations = [
            (1, 0.95),  # Mock content from category 1
            (2, 0.90),  # Mock content from category 1
            (3, 0.85),  # Mock content from category 1
            (4, 0.80),  # Mock content from category 2
            (5, 0.75),  # Mock content from category 2
        ]

        user_profile = {"preferred_categories": [1]}

        optimized = await algorithm._optimize_diversity(recommendations, user_profile)

        # Verify optimization
        assert len(optimized) == len(recommendations)

        # Should maintain some diversity (not all from same category)
        # This is a simplified test - real implementation would check actual content metadata
        assert len(optimized) > 0

    @pytest.mark.asyncio
    async def test_fallback_mechanism(self, algorithm):
        """Test fallback when main algorithms fail."""
        # Mock algorithm failures
        algorithm._get_algorithm_recommendations = AsyncMock(
            side_effect=Exception("Algorithm failure")
        )

        result = await algorithm._get_fallback_recommendations(
            user_id=1, num_recommendations=5
        )

        # Should return valid result even on failure
        assert isinstance(result, RecommendationResult)
        assert result.user_id == 1

    @pytest.mark.asyncio
    async def test_full_recommendation_generation(self, algorithm):
        """Test complete recommendation generation flow."""
        # Mock user profile analysis
        algorithm._analyze_user_profile = AsyncMock(
            return_value={
                "user_id": 1,
                "total_interactions": 25,
                "personalization_level": "medium",
                "is_new_user": False,
            }
        )

        # Mock algorithm results
        mock_results = {
            "content_based": RecommendationResult([1, 2], [0.9, 0.8], "content", 1),
            "collaborative": RecommendationResult([2, 3], [0.85, 0.75], "collab", 1),
            "trending": RecommendationResult([3, 4], [0.95, 0.85], "trending", 1),
        }
        algorithm._get_algorithm_recommendations = AsyncMock(return_value=mock_results)

        # Generate recommendations
        result = await algorithm.generate_recommendations(
            user_id=1, num_recommendations=3
        )

        # Verify result
        assert isinstance(result, RecommendationResult)
        assert result.user_id == 1
        assert len(result.content_ids) <= 3
        assert result.algorithm_name == "Hybrid Recommendation System"

        # Verify metadata includes algorithm information
        assert "algorithm_weights" in result.metadata
        assert "user_profile_summary" in result.metadata
        assert "algorithm_contributions" in result.metadata

    @pytest.mark.asyncio
    async def test_recommendation_explanation(self, algorithm):
        """Test hybrid recommendation explanation."""
        # Mock individual algorithm explanations
        algorithm.content_based.explain_recommendation = AsyncMock(
            return_value={
                "algorithm": "content_based",
                "confidence": 0.85,
                "reasons": ["Similar to your interests"],
            }
        )

        algorithm.collaborative.explain_recommendation = AsyncMock(
            return_value={
                "algorithm": "collaborative",
                "confidence": 0.78,
                "reasons": ["Users like you also liked this"],
            }
        )

        explanation = await algorithm.explain_recommendation(user_id=1, content_id=1)

        # Verify explanation structure
        assert "content_id" in explanation
        assert "algorithm" in explanation
        assert "contributing_algorithms" in explanation
        assert "detailed_explanations" in explanation
        assert explanation["content_id"] == 1


@pytest.mark.unit
@pytest.mark.algorithms
class TestABTestingHybridRecommendation:
    """Test A/B testing variant of hybrid algorithm."""

    @pytest.fixture
    def ab_algorithm(self, mock_db):
        """Create A/B testing hybrid algorithm."""
        return ABTestingHybridRecommendation(mock_db)

    def test_user_variant_assignment(self, ab_algorithm):
        """Test consistent user variant assignment."""
        # Test that same user always gets same variant
        variant1 = ab_algorithm._get_user_variant(user_id=1)
        variant2 = ab_algorithm._get_user_variant(user_id=1)

        assert variant1 == variant2

        # Test that different users can get different variants
        variants = set()
        for user_id in range(1, 20):
            variant = ab_algorithm._get_user_variant(user_id)
            variants.add(variant)

        # Should have multiple variants
        assert len(variants) > 1

        # All variants should be valid
        valid_variants = [
            "control",
            "content_heavy",
            "collaborative_heavy",
            "trending_heavy",
        ]
        assert all(v in valid_variants for v in variants)

    @pytest.mark.asyncio
    async def test_variant_weight_application(self, ab_algorithm):
        """Test that A/B variants apply correct weights."""
        # Mock parent class methods
        ab_algorithm._analyze_user_profile = AsyncMock(
            return_value={"user_id": 1, "personalization_level": "medium"}
        )

        mock_results = {
            "content_based": RecommendationResult([1], [0.9], "content", 1),
            "collaborative": RecommendationResult([2], [0.8], "collab", 1),
            "trending": RecommendationResult([3], [0.7], "trending", 1),
        }
        ab_algorithm._get_algorithm_recommendations = AsyncMock(
            return_value=mock_results
        )
        ab_algorithm._combine_algorithm_results = AsyncMock(return_value=[(1, 0.9)])
        ab_algorithm._optimize_diversity = AsyncMock(return_value=[(1, 0.9)])

        # Test different user IDs to get different variants
        for user_id in [1, 2, 3, 4]:  # Should cover different variants
            result = await ab_algorithm.generate_recommendations(user_id=user_id)

            assert isinstance(result, RecommendationResult)
            assert "ab_test_variant" in result.metadata
            assert "Variant:" in result.algorithm_name
