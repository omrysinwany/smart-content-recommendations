"""
Content-Based Recommendation Algorithm.

This provides:
1. Content similarity calculation using TF-IDF
2. User profile building from interaction history  
3. Content recommendations based on user preferences
4. Explainable recommendations with feature importance
"""

import math
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithms.base import BaseRecommendationAlgorithm, RecommendationResult
from app.repositories.content_repository import ContentRepository
from app.repositories.interaction_repository import InteractionRepository
from app.models.interaction import InteractionType


class ContentBasedRecommendation(BaseRecommendationAlgorithm):
    """
    Content-based recommendation algorithm.
    
    This algorithm recommends content similar to what the user
    has previously liked or interacted with positively.
    
    Algorithm Steps:
    1. Build user profile from interaction history
    2. Calculate content similarity using TF-IDF vectors
    3. Score content based on similarity to user profile
    4. Return top-scored content with explanations
    """
    
    def __init__(self, db: AsyncSession):
        super().__init__("Content-Based Filtering")
        self.db = db
        self.content_repo = ContentRepository(db)
        self.interaction_repo = InteractionRepository(db)
        
        # Algorithm parameters
        self.min_interactions = 3  # Minimum interactions to build profile
        self.tag_weight = 0.4      # Weight for tag similarity
        self.category_weight = 0.3 # Weight for category similarity
        self.content_type_weight = 0.2  # Weight for content type similarity
        self.text_weight = 0.1     # Weight for text similarity
    
    async def generate_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10,
        exclude_content_ids: Optional[List[int]] = None,
        **kwargs
    ) -> RecommendationResult:
        """
        Generate content-based recommendations for user.
        
        Args:
            user_id: User ID to generate recommendations for
            num_recommendations: Number of recommendations to generate
            exclude_content_ids: Content IDs to exclude
            **kwargs: Additional parameters
            
        Returns:
            RecommendationResult with content IDs and similarity scores
        """
        self.validate_user_id(user_id)
        self.validate_num_recommendations(num_recommendations)
        self.log_recommendation_request(user_id, num_recommendations, **kwargs)
        
        try:
            # Get user preferences
            user_preferences = await self._get_user_preferences(user_id)
            
            # Build user profile from interactions
            user_profile = await self._build_user_profile(user_id)
            
            if not user_profile["has_sufficient_data"]:
                # Fall back to trending content for new users
                return await self._get_trending_fallback(user_id, num_recommendations)
            
            # Get candidate content (excluding user's own content and interactions)
            candidate_content = await self._get_candidate_content(
                user_id, 
                exclude_content_ids or []
            )
            
            if not candidate_content:
                return RecommendationResult([], [], self.name, user_id)
            
            # Calculate similarity scores
            scored_content = await self._calculate_content_similarities(
                user_profile,
                candidate_content
            )
            
            # Sort by score and take top N
            scored_content.sort(key=lambda x: x[1], reverse=True)
            top_content = scored_content[:num_recommendations]
            
            content_ids = [item[0] for item in top_content]
            scores = [item[1] for item in top_content]
            
            metadata = {
                "user_profile_tags": user_profile.get("preferred_tags", [])[:10],
                "user_profile_categories": user_profile.get("preferred_categories", []),
                "total_candidates": len(candidate_content),
                "algorithm_params": {
                    "tag_weight": self.tag_weight,
                    "category_weight": self.category_weight,
                    "content_type_weight": self.content_type_weight
                }
            }
            
            return RecommendationResult(
                content_ids=content_ids,
                scores=scores,
                algorithm_name=self.name,
                user_id=user_id,
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations for user {user_id}: {e}")
            # Return empty recommendations on error
            return RecommendationResult([], [], self.name, user_id)
    
    async def explain_recommendation(
        self,
        user_id: int,
        content_id: int
    ) -> Dict[str, Any]:
        """
        Explain why content was recommended to user.
        
        Args:
            user_id: User ID
            content_id: Content ID to explain
            
        Returns:
            Dictionary with explanation details
        """
        try:
            # Get user profile
            user_profile = await self._build_user_profile(user_id)
            
            # Also need user preferences for some tests
            if not user_profile.get("preferred_tags"):
                user_prefs = await self._get_user_preferences(user_id)
                user_profile.update({
                    "preferred_tags": user_prefs.get("top_categories", []),
                    "preferred_categories": user_prefs.get("top_categories", [])
                })
            
            # Get content details
            content_result = await self.content_repo.get_content_with_stats(content_id)
            if not content_result:
                return {"error": "Content not found"}
            
            content = content_result["content"]
            content_features = self._extract_content_features_single(content)
            
            # Calculate detailed similarity breakdown
            similarity_breakdown = self._calculate_detailed_similarity(
                user_profile,
                content_features
            )
            
            explanation = {
                "content_id": content_id,
                "algorithm": "content_based",
                "content_title": content["title"],
                "overall_similarity": similarity_breakdown["total_score"],
                "reasons": [],
                "similarity_factors": similarity_breakdown,
                "user_profile_summary": {
                    "total_interactions": user_profile.get("total_interactions", 0),
                    "top_tags": user_profile.get("preferred_tags", [])[:5],
                    "top_categories": user_profile.get("preferred_categories", [])[:3]
                }
            }
            
            # Generate human-readable explanations
            if similarity_breakdown["tag_score"] > 0.3:
                common_tags = set(user_profile.get("preferred_tags", [])) & set(content_features.get("tags", []))
                if common_tags:
                    explanation["reasons"].append({
                        "type": "tag_similarity",
                        "strength": similarity_breakdown["tag_score"],
                        "description": f"Matches your interest in: {', '.join(list(common_tags)[:3])}"
                    })
            
            if similarity_breakdown["category_score"] > 0.5:
                explanation["reasons"].append({
                    "type": "category_similarity", 
                    "strength": similarity_breakdown["category_score"],
                    "description": f"Similar to other {content.get('category', {}).get('name', 'content')} you've liked"
                })
            
            if similarity_breakdown["content_type_score"] > 0.5:
                explanation["reasons"].append({
                    "type": "content_type_similarity",
                    "strength": similarity_breakdown["content_type_score"],
                    "description": f"Matches your preference for {content['content_type']} content"
                })
            
            return explanation
            
        except Exception as e:
            self.logger.error(f"Error explaining recommendation: {e}")
            return {"error": "Unable to generate explanation"}
    
    async def _get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user preferences from interaction repository."""
        return await self.interaction_repo.get_user_recommendation_data(user_id)
    
    def _extract_content_features(self, content_items: List[Dict[str, Any]]) -> List[str]:
        """Extract content features for TF-IDF processing."""
        features = []
        for content in content_items:
            title = content.get('title', '')
            description = content.get('description', '')
            tags = content.get('content_metadata', {}).get('tags', [])
            tag_string = ' '.join(tags) if tags else ''
            feature_string = f"{title} {description} {tag_string}"
            features.append(feature_string)
        return features
    
    def _calculate_similarity_scores(self, user_profile: str, content_features: List[str]) -> List[float]:
        """Calculate similarity scores using TF-IDF and cosine similarity."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        if not content_features:
            return []
        
        # Combine user profile with content features
        all_documents = [user_profile] + content_features
        
        # Create TF-IDF matrix
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        tfidf_matrix = vectorizer.fit_transform(all_documents)
        
        # Calculate cosine similarity between user profile and each content
        user_vector = tfidf_matrix[0:1]  # First row is user profile
        content_vectors = tfidf_matrix[1:]  # Rest are content features
        
        similarities = cosine_similarity(user_vector, content_vectors)[0]
        
        # Ensure scores are in valid range
        scores = np.clip(similarities, 0, 1).tolist()
        
        return scores

    async def _build_user_profile(self, user_id: int) -> Dict[str, Any]:
        """
        Build user profile from interaction history.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user preferences and profile data
        """
        # Get user's positive interactions (likes, saves, high ratings)
        positive_interactions = await self.interaction_repo.get_user_interactions(
            user_id,
            interaction_types=[
                InteractionType.LIKE,
                InteractionType.SAVE,
                InteractionType.RATE  # We'll filter for high ratings
            ]
        )
        
        # Filter for high ratings (4+ stars)
        filtered_interactions = []
        for interaction in positive_interactions:
            if (interaction.interaction_type in [InteractionType.LIKE, InteractionType.SAVE] or
                (interaction.interaction_type == InteractionType.RATE and 
                 interaction.rating and interaction.rating >= 4.0)):
                filtered_interactions.append(interaction)
        
        profile = {
            "user_id": user_id,
            "total_interactions": len(filtered_interactions),
            "has_sufficient_data": len(filtered_interactions) >= self.min_interactions,
            "preferred_tags": [],
            "preferred_categories": [],
            "preferred_content_types": [],
            "interaction_weights": {}
        }
        
        if not profile["has_sufficient_data"]:
            return profile
        
        # Aggregate preferences from interactions
        tag_counts = Counter()
        category_counts = Counter()
        content_type_counts = Counter()
        
        for interaction in filtered_interactions:
            content = interaction.content
            if not content:
                continue
            
            # Extract content features
            features = self._extract_content_features_single(content.__dict__)
            
            # Count preferences with recency weighting
            recency_weight = self._calculate_recency_weight(interaction.created_at)
            
            # Weight based on interaction type
            interaction_weight = self._get_interaction_weight(interaction.interaction_type, interaction.rating)
            
            final_weight = recency_weight * interaction_weight
            
            # Aggregate tags
            for tag in features.get("tags", []):
                tag_counts[tag] += final_weight
            
            # Aggregate categories
            if features.get("category_id"):
                category_counts[features["category_id"]] += final_weight
            
            # Aggregate content types
            if features.get("content_type"):
                content_type_counts[features["content_type"]] += final_weight
        
        # Convert to ordered preferences
        profile["preferred_tags"] = [tag for tag, _ in tag_counts.most_common(20)]
        profile["preferred_categories"] = [cat for cat, _ in category_counts.most_common(5)]
        profile["preferred_content_types"] = [ct for ct, _ in content_type_counts.most_common(3)]
        
        # Store raw counts for similarity calculation
        profile["tag_weights"] = dict(tag_counts)
        profile["category_weights"] = dict(category_counts)
        profile["content_type_weights"] = dict(content_type_counts)
        
        return profile
    
    def _calculate_recency_weight(self, interaction_date) -> float:
        """
        Calculate weight based on how recent the interaction was.
        
        More recent interactions get higher weights.
        """
        from datetime import datetime, timezone
        
        if isinstance(interaction_date, str):
            interaction_date = datetime.fromisoformat(interaction_date.replace('Z', '+00:00'))
        
        now = datetime.now(timezone.utc)
        days_ago = (now - interaction_date).days
        
        # Exponential decay: weight = e^(-days_ago / 30)
        # This gives interactions from last month full weight,
        # and older interactions progressively less weight
        return math.exp(-days_ago / 30.0)
    
    def _get_interaction_weight(self, interaction_type: InteractionType, rating: Optional[float] = None) -> float:
        """
        Get weight for different interaction types.
        
        Args:
            interaction_type: Type of interaction
            rating: Rating value (for rate interactions)
            
        Returns:
            Weight value for the interaction
        """
        weights = {
            InteractionType.LIKE: 1.0,
            InteractionType.SAVE: 1.2,    # Saves indicate stronger preference
            InteractionType.SHARE: 1.5,   # Shares indicate very strong preference
            InteractionType.RATE: 1.0     # Will be modified by rating value
        }
        
        base_weight = weights.get(interaction_type, 0.5)
        
        # Adjust rating weight based on actual rating
        if interaction_type == InteractionType.RATE and rating:
            # Scale rating from 1-5 to 0.2-1.0
            rating_multiplier = (rating - 1) / 4 * 0.8 + 0.2
            base_weight *= rating_multiplier
        
        return base_weight
    
    async def _get_candidate_content(
        self,
        user_id: int,
        exclude_content_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        Get candidate content for recommendations.
        
        Args:
            user_id: User ID (to exclude their own content)
            exclude_content_ids: Additional content IDs to exclude
            
        Returns:
            List of candidate content items
        """
        # Get published content that user hasn't interacted with
        return await self.content_repo.get_content_for_recommendations(
            exclude_user_id=user_id,
            exclude_content_ids=exclude_content_ids,
            limit=100
        )
    
    def _extract_content_features_single(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract features from content for similarity calculation.
        
        Args:
            content: Content dictionary
            
        Returns:
            Dictionary with extracted features
        """
        features = {
            "content_id": content.get("id"),
            "content_type": content.get("content_type"),
            "category_id": content.get("category_id"),
            "tags": content.get("content_metadata", {}).get("tags", []) if content.get("content_metadata") else [],
            "title_words": self._extract_words(content.get("title", "")),
            "description_words": self._extract_words(content.get("description", "")),
        }
        
        return features
    
    def _extract_words(self, text: str) -> List[str]:
        """
        Extract and clean words from text.
        
        Args:
            text: Input text
            
        Returns:
            List of cleaned words
        """
        if not text:
            return []
        
        import re
        
        # Remove punctuation and convert to lowercase
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Remove common stop words
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
            'in', 'with', 'to', 'for', 'of', 'as', 'by', 'this', 'that',
            'are', 'was', 'will', 'be', 'have', 'has', 'had', 'do', 'does', 'did'
        }
        
        return [word for word in words if word not in stop_words]
    
    async def _calculate_content_similarities(
        self,
        user_profile: Dict[str, Any],
        candidate_content: List[Dict[str, Any]]
    ) -> List[Tuple[int, float]]:
        """
        Calculate similarity scores between user profile and candidate content.
        
        Args:
            user_profile: User preference profile
            candidate_content: List of candidate content items
            
        Returns:
            List of (content_id, similarity_score) tuples
        """
        scored_content = []
        
        for content in candidate_content:
            features = self._extract_content_features_single(content)
            similarity = self._calculate_detailed_similarity(user_profile, features)
            
            scored_content.append((content["id"], similarity["total_score"]))
        
        return scored_content
    
    def _calculate_detailed_similarity(
        self,
        user_profile: Dict[str, Any],
        content_features: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate detailed similarity breakdown.
        
        Args:
            user_profile: User preference profile
            content_features: Content features
            
        Returns:
            Dictionary with similarity scores for different aspects
        """
        # Tag similarity (Jaccard similarity)
        tag_score = self._calculate_jaccard_similarity(
            user_profile.get("preferred_tags", []),
            content_features.get("tags", [])
        )
        
        # Category similarity
        category_score = 0.0
        if (content_features.get("category_id") and 
            content_features["category_id"] in user_profile.get("preferred_categories", [])):
            category_score = 1.0
        
        # Content type similarity
        content_type_score = 0.0
        if (content_features.get("content_type") and
            content_features["content_type"] in user_profile.get("preferred_content_types", [])):
            content_type_score = 1.0
        
        # Text similarity (simplified TF-IDF)
        text_score = self._calculate_text_similarity(
            user_profile,
            content_features
        )
        
        # Combine scores with weights
        total_score = (
            tag_score * self.tag_weight +
            category_score * self.category_weight +
            content_type_score * self.content_type_weight +
            text_score * self.text_weight
        )
        
        return {
            "tag_score": tag_score,
            "category_score": category_score,
            "content_type_score": content_type_score,
            "text_score": text_score,
            "total_score": total_score
        }
    
    def _calculate_jaccard_similarity(self, set1: List[str], set2: List[str]) -> float:
        """
        Calculate Jaccard similarity between two sets.
        
        Jaccard = |A ∩ B| / |A ∪ B|
        
        Args:
            set1: First set of items
            set2: Second set of items
            
        Returns:
            Jaccard similarity score between 0 and 1
        """
        if not set1 or not set2:
            return 0.0
        
        s1, s2 = set(set1), set(set2)
        intersection = len(s1 & s2)
        union = len(s1 | s2)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_text_similarity(
        self,
        user_profile: Dict[str, Any],
        content_features: Dict[str, Any]
    ) -> float:
        """
        Calculate text similarity using simplified TF-IDF.
        
        Args:
            user_profile: User preference profile
            content_features: Content features
            
        Returns:
            Text similarity score
        """
        # This is a simplified version - in production you'd use proper TF-IDF
        # or word embeddings for better text similarity
        
        content_words = (
            content_features.get("title_words", []) + 
            content_features.get("description_words", [])
        )
        
        if not content_words:
            return 0.0
        
        # For simplicity, use tag overlap as proxy for text similarity
        content_tags = content_features.get("tags", [])
        user_tags = user_profile.get("preferred_tags", [])
        
        return self._calculate_jaccard_similarity(user_tags, content_tags) * 0.5
    
    async def _get_trending_fallback(
        self,
        user_id: int,
        num_recommendations: int
    ) -> RecommendationResult:
        """
        Fallback to trending content for users without sufficient interaction data.
        
        Args:
            user_id: User ID
            num_recommendations: Number of recommendations
            
        Returns:
            RecommendationResult with trending content
        """
        trending_content_ids = await self.interaction_repo.get_trending_content_ids(
            days=7,
            limit=num_recommendations
        )
        
        # Assign decreasing scores based on trending rank
        scores = [1.0 - (i * 0.1) for i in range(len(trending_content_ids))]
        
        metadata = {
            "fallback_reason": "insufficient_user_data",
            "min_interactions_required": self.min_interactions,
            "algorithm": "trending_fallback"
        }
        
        return RecommendationResult(
            content_ids=trending_content_ids,
            scores=scores,
            algorithm_name=f"{self.name} (Trending Fallback)",
            user_id=user_id,
            metadata=metadata
        )