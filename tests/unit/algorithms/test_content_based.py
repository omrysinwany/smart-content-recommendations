"""
Unit tests for Content-Based Recommendation Algorithm.
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, Mock
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.algorithms.content_based import ContentBasedRecommendation
from app.algorithms.base import RecommendationResult


@pytest.mark.unit
@pytest.mark.algorithms
class TestContentBasedRecommendation:
    """Test content-based filtering algorithm."""
    
    @pytest.fixture
    def algorithm(self, mock_db):
        """Create content-based algorithm instance."""
        return ContentBasedRecommendation(mock_db)
    
    def test_tfidf_similarity_calculation(self, algorithm):
        """Test TF-IDF similarity calculation accuracy."""
        # Test documents with known similarity patterns
        documents = [
            "python machine learning data science artificial intelligence",
            "javascript react frontend web development user interface",
            "python web development fastapi backend api",
            "machine learning artificial intelligence neural networks"
        ]
        
        # Calculate TF-IDF matrix
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(documents)
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # Verify similarity patterns
        assert similarity_matrix.shape == (4, 4)
        
        # Python docs (0 and 2) should be more similar than python and javascript (0 and 1)
        assert similarity_matrix[0, 2] > similarity_matrix[0, 1]
        
        # ML docs (0 and 3) should be highly similar
        assert similarity_matrix[0, 3] > 0.3
        
        # All similarities should be in valid range [0, 1] (with floating point tolerance)
        assert np.all((similarity_matrix >= -1e-10) & (similarity_matrix <= 1.0 + 1e-10))
        
        # Diagonal should be 1 (self-similarity)
        assert np.allclose(np.diag(similarity_matrix), 1.0)
    
    @pytest.mark.asyncio
    async def test_get_user_preferences(self, algorithm):
        """Test user preference extraction from interactions."""
        # Mock user interaction data
        algorithm.interaction_repo.get_user_recommendation_data = AsyncMock(return_value={
            "preferred_content_types": ["article", "video"],
            "top_categories": [1, 3, 5],
            "interaction_summary": {"likes": 10, "views": 50, "saves": 5},
            "total_interactions": 65
        })
        
        preferences = await algorithm._get_user_preferences(user_id=1)
        
        # Verify preferences structure
        assert "preferred_content_types" in preferences
        assert "top_categories" in preferences
        assert "interaction_summary" in preferences
        assert preferences["total_interactions"] == 65
        
        # Verify method was called correctly
        algorithm.interaction_repo.get_user_recommendation_data.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_recommendation_generation_with_data(self, algorithm):
        """Test recommendation generation with mock data."""
        # Mock user preferences
        algorithm._get_user_preferences = AsyncMock(return_value={
            "preferred_content_types": ["article"],
            "top_categories": [1, 2],
            "interaction_summary": {"likes": 5, "views": 20},
            "total_interactions": 25
        })
        
        # Mock content features
        algorithm.content_repo.get_content_for_recommendations = AsyncMock(return_value=[
            {
                "id": 1,
                "title": "Python Programming Guide",
                "description": "Learn Python programming fundamentals",
                "content_metadata": {"tags": ["python", "programming"]},
                "category_id": 1
            },
            {
                "id": 2,
                "title": "Web Development with FastAPI",
                "description": "Build APIs with FastAPI framework",
                "content_metadata": {"tags": ["python", "web", "api"]},
                "category_id": 1
            },
            {
                "id": 3,
                "title": "JavaScript Frontend",
                "description": "Frontend development with JavaScript",
                "content_metadata": {"tags": ["javascript", "frontend"]},
                "category_id": 2
            }
        ])
        
        # Generate recommendations
        result = await algorithm.generate_recommendations(
            user_id=1,
            num_recommendations=3
        )
        
        # Verify result structure
        assert isinstance(result, RecommendationResult)
        assert len(result.content_ids) <= 3
        assert len(result.scores) == len(result.content_ids)
        assert result.algorithm_name == "Content-Based Filtering"
        assert result.user_id == 1
        
        # Verify scores are valid
        assert all(0 <= score <= 1 for score in result.scores)
        
        # Verify scores are sorted in descending order
        assert all(result.scores[i] >= result.scores[i+1] for i in range(len(result.scores)-1))
    
    @pytest.mark.asyncio
    async def test_recommendation_with_no_interactions(self, algorithm):
        """Test recommendations for users with no interaction history."""
        # Mock empty user preferences
        algorithm._get_user_preferences = AsyncMock(return_value={
            "preferred_content_types": [],
            "top_categories": [],
            "interaction_summary": {},
            "total_interactions": 0
        })
        
        # Mock trending content fallback
        algorithm.content_repo.get_trending_content = AsyncMock(return_value=[
            {"id": 1, "title": "Trending Article 1"},
            {"id": 2, "title": "Trending Article 2"}
        ])
        
        result = await algorithm.generate_recommendations(
            user_id=1,
            num_recommendations=5
        )
        
        # Should fall back to trending content
        assert isinstance(result, RecommendationResult)
        assert len(result.content_ids) <= 5
    
    @pytest.mark.asyncio
    async def test_explain_recommendation(self, algorithm):
        """Test recommendation explanation generation."""
        # Mock content details
        algorithm.content_repo.get_content_with_stats = AsyncMock(return_value={
            "content": {
                "id": 1,
                "title": "Python Machine Learning",
                "content_metadata": {"tags": ["python", "ml", "data-science"]}
            },
            "stats": {"views": 1000, "likes": 85}
        })
        
        # Mock user preferences
        algorithm._get_user_preferences = AsyncMock(return_value={
            "preferred_content_types": ["article"],
            "top_categories": [1],
            "interaction_summary": {"likes": 10, "views": 50}
        })
        
        # Mock user interactions for _build_user_profile
        algorithm.interaction_repo.get_user_interactions = AsyncMock(return_value=[])
        
        explanation = await algorithm.explain_recommendation(user_id=1, content_id=1)
        
        # Verify explanation structure
        assert "content_id" in explanation
        assert "algorithm" in explanation
        assert "reasons" in explanation
        assert "similarity_factors" in explanation
        assert explanation["content_id"] == 1
        assert explanation["algorithm"] == "content_based"
    
    def test_content_feature_extraction(self, algorithm):
        """Test content feature extraction and processing."""
        content_items = [
            {
                "id": 1,
                "title": "Python Programming",
                "description": "Learn Python basics",
                "content_metadata": {"tags": ["python", "programming"]}
            },
            {
                "id": 2,
                "title": "Web Development",
                "description": "Build web applications", 
                "content_metadata": {"tags": ["web", "development"]}
            }
        ]
        
        features = algorithm._extract_content_features(content_items)
        
        # Verify feature extraction
        assert len(features) == 2
        assert ("python" in features[0].lower() or "programming" in features[0].lower())
        assert ("web" in features[1].lower() or "development" in features[1].lower())
    
    @pytest.mark.asyncio
    async def test_error_handling(self, algorithm):
        """Test error handling in recommendation generation."""
        # Mock repository to raise exception
        algorithm.content_repo.get_content_for_recommendations = AsyncMock(
            side_effect=Exception("Database connection error")
        )
        
        # Should handle errors gracefully
        result = await algorithm.generate_recommendations(user_id=1, num_recommendations=5)
        
        # Should return empty result, not raise exception
        assert isinstance(result, RecommendationResult)
        assert len(result.content_ids) == 0
    
    def test_similarity_score_calculation(self, algorithm):
        """Test similarity score calculation between user profile and content."""
        user_profile = "python machine learning data science"
        content_features = [
            "python programming tutorial beginner",
            "machine learning algorithms neural networks",
            "javascript frontend development react",
            "data science analytics visualization"
        ]
        
        scores = algorithm._calculate_similarity_scores(user_profile, content_features)
        
        # Verify scores
        assert len(scores) == 4
        assert all(0 <= score <= 1 for score in scores)
        
        # Python and ML content should have higher scores
        assert scores[0] > scores[2]  # Python content > JavaScript content
        assert scores[1] > scores[2]  # ML content > JavaScript content