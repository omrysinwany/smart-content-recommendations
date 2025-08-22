#!/usr/bin/env python3
"""
Smart Content Recommendations - Production System Test

This script demonstrates the complete recommendation system working with
a real database, showing all the algorithms and features in action.

Usage:
    python test_production_system.py
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import our application components
from app.database import Base
from app.models.user import User
from app.models.content import Content, ContentCategory, ContentType
from app.models.interaction import Interaction, InteractionType
from app.services.recommendation_service import RecommendationService
from app.core.cache import init_cache, cleanup_cache


class ProductionSystemTest:
    """Test the complete recommendation system in a production-like environment."""
    
    def __init__(self, database_url: str = "sqlite+aiosqlite:///./test_production.db"):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
        
    async def setup_database(self):
        """Initialize database connection and create tables."""
        logger.info("🗄️  Setting up database connection...")
        
        # Create async engine
        self.engine = create_async_engine(
            self.database_url,
            echo=False  # Set to True for SQL debugging
        )
        
        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session factory
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        
        logger.info("✅ Database setup complete!")
    
    async def seed_sample_data(self):
        """Create comprehensive sample data for testing."""
        logger.info("🌱 Seeding sample data...")
        
        async with self.session_factory() as session:
            # Create categories
            categories = [
                ContentCategory(
                    name="Technology",
                    slug="technology",
                    description="Latest tech trends and programming"
                ),
                ContentCategory(
                    name="Science",
                    slug="science",
                    description="Scientific discoveries and research"
                ),
                ContentCategory(
                    name="Business",
                    slug="business",
                    description="Business strategies and entrepreneurship"
                ),
                ContentCategory(
                    name="Health",
                    slug="health",
                    description="Health and wellness content"
                ),
            ]
            
            session.add_all(categories)
            await session.flush()
            
            # Create users with diverse profiles
            users = [
                User(
                    email="alice.tech@example.com",
                    full_name="Alice Johnson",
                    hashed_password="hashed_password_1",
                    bio="Software engineer passionate about AI and machine learning",
                    preferences={"interests": ["python", "ai", "ml"], "difficulty": "advanced"}
                ),
                User(
                    email="bob.science@example.com",
                    full_name="Bob Smith",
                    hashed_password="hashed_password_2",
                    bio="Data scientist interested in research and analytics",
                    preferences={"interests": ["data-science", "statistics"], "difficulty": "intermediate"}
                ),
                User(
                    email="charlie.newbie@example.com",
                    full_name="Charlie Brown",
                    hashed_password="hashed_password_3",
                    bio="New to tech, eager to learn programming",
                    preferences={"interests": ["programming", "web-dev"], "difficulty": "beginner"}
                ),
                User(
                    email="diana.business@example.com",
                    full_name="Diana Wilson",
                    hashed_password="hashed_password_4",
                    bio="Business analyst with tech interests",
                    preferences={"interests": ["business", "analytics"], "difficulty": "intermediate"}
                ),
            ]
            
            session.add_all(users)
            await session.flush()
            
            # Create diverse content
            contents = [
                # Technology content
                Content(
                    title="Advanced Python Techniques for AI Development",
                    description="Deep dive into Python patterns used in AI development",
                    body="Comprehensive guide covering decorators, metaclasses, and async patterns...",
                    content_type=ContentType.ARTICLE,
                    author_id=users[0].id,
                    category_id=categories[0].id,
                    content_metadata={
                        "tags": ["python", "ai", "advanced", "patterns"],
                        "difficulty": "advanced",
                        "estimated_read_time": 15
                    },
                    is_published=True,
                    view_count=1250,
                    like_count=89,
                    trending_score=0.85
                ),
                Content(
                    title="Machine Learning Fundamentals with Scikit-learn",
                    description="Learn ML basics with practical examples",
                    body="Introduction to supervised and unsupervised learning...",
                    content_type=ContentType.COURSE,
                    author_id=users[1].id,
                    category_id=categories[0].id,
                    content_metadata={
                        "tags": ["machine-learning", "scikit-learn", "beginner"],
                        "difficulty": "beginner",
                        "duration_hours": 8
                    },
                    is_published=True,
                    view_count=2100,
                    like_count=156,
                    trending_score=0.92
                ),
                Content(
                    title="Building REST APIs with FastAPI",
                    description="Complete guide to building production-ready APIs",
                    body="Step-by-step tutorial for creating robust web APIs...",
                    content_type=ContentType.VIDEO,
                    author_id=users[0].id,
                    category_id=categories[0].id,
                    content_metadata={
                        "tags": ["fastapi", "python", "web-development", "api"],
                        "difficulty": "intermediate",
                        "duration_minutes": 45
                    },
                    is_published=True,
                    view_count=890,
                    like_count=67,
                    trending_score=0.78
                ),
                # Science content
                Content(
                    title="Data Science in Climate Research",
                    description="How data science is revolutionizing climate studies",
                    body="Exploring the intersection of data science and environmental research...",
                    content_type=ContentType.ARTICLE,
                    author_id=users[1].id,
                    category_id=categories[1].id,
                    content_metadata={
                        "tags": ["data-science", "climate", "research", "environment"],
                        "difficulty": "intermediate",
                        "estimated_read_time": 12
                    },
                    is_published=True,
                    view_count=756,
                    like_count=42,
                    trending_score=0.65
                ),
                # Business content
                Content(
                    title="Data-Driven Business Strategies",
                    description="Using analytics to drive business decisions",
                    body="How modern businesses leverage data for competitive advantage...",
                    content_type=ContentType.ARTICLE,
                    author_id=users[3].id,
                    category_id=categories[2].id,
                    content_metadata={
                        "tags": ["business", "analytics", "strategy", "data"],
                        "difficulty": "intermediate",
                        "estimated_read_time": 10
                    },
                    is_published=True,
                    view_count=445,
                    like_count=28,
                    trending_score=0.58
                ),
            ]
            
            session.add_all(contents)
            await session.flush()
            
            # Create realistic interaction patterns
            interactions = [
                # Alice (tech expert) - likes advanced content
                Interaction(user_id=users[0].id, content_id=contents[0].id, interaction_type=InteractionType.LIKE),
                Interaction(user_id=users[0].id, content_id=contents[2].id, interaction_type=InteractionType.LIKE),
                
                # Bob (data scientist) - interested in both tech and science
                Interaction(user_id=users[1].id, content_id=contents[1].id, interaction_type=InteractionType.LIKE),
                Interaction(user_id=users[1].id, content_id=contents[1].id, interaction_type=InteractionType.RATE, rating=5.0),
                Interaction(user_id=users[1].id, content_id=contents[3].id, interaction_type=InteractionType.LIKE),
                
                # Charlie (newbie) - focuses on beginner content
                Interaction(user_id=users[2].id, content_id=contents[1].id, interaction_type=InteractionType.LIKE),
                
                # Diana (business) - interested in business and some tech
                Interaction(user_id=users[3].id, content_id=contents[4].id, interaction_type=InteractionType.LIKE),
                Interaction(user_id=users[3].id, content_id=contents[4].id, interaction_type=InteractionType.SHARE),
            ]
            
            session.add_all(interactions)
            await session.commit()
            
            logger.info(f"✅ Created {len(categories)} categories, {len(users)} users, {len(contents)} content items, {len(interactions)} interactions")
    
    async def test_recommendation_algorithms(self):
        """Test all recommendation algorithms with real data."""
        logger.info("🧠 Testing recommendation algorithms...")
        
        async with self.session_factory() as session:
            service = RecommendationService(session)
            
            # Test different scenarios
            test_scenarios = [
                {
                    "name": "Tech Expert (Alice)",
                    "user_id": 1,
                    "expected": "Should get advanced tech content recommendations"
                },
                {
                    "name": "Data Scientist (Bob)",
                    "user_id": 2,
                    "expected": "Should get ML/data science content"
                },
                {
                    "name": "Newbie (Charlie)",
                    "user_id": 3,
                    "expected": "Should get beginner-friendly content"
                },
                {
                    "name": "Business Analyst (Diana)",
                    "user_id": 4,
                    "expected": "Should get business + some data content"
                }
            ]
            
            results = {}
            
            for scenario in test_scenarios:
                logger.info(f"\n🔬 Testing: {scenario['name']}")
                logger.info(f"📋 Expected: {scenario['expected']}")
                
                # Get user recommendations
                recommendations = await service.get_user_recommendations(
                    user_id=scenario["user_id"],
                    algorithm="auto",  # Let system choose best algorithm
                    num_recommendations=5
                )
                
                logger.info(f"🎯 Algorithm used: {recommendations['algorithm']}")
                logger.info(f"📊 Recommendations count: {len(recommendations['recommendations'])}")
                
                if recommendations['recommendations']:
                    logger.info("📚 Recommended content:")
                    for i, rec in enumerate(recommendations['recommendations'][:3], 1):
                        logger.info(f"  {i}. {rec['title']} (score: {rec['recommendation_score']:.3f})")
                
                # Test explanation
                if recommendations['recommendations']:
                    first_content_id = recommendations['recommendations'][0]['content_id']
                    explanation = await service.explain_recommendation(
                        user_id=scenario["user_id"],
                        content_id=first_content_id,
                        algorithm=recommendations['algorithm']
                    )
                    if 'error' not in explanation:
                        logger.info(f"💡 Explanation available for content {first_content_id}")
                
                results[scenario['name']] = recommendations
            
            # Test trending content
            logger.info("\n🔥 Testing Trending Content:")
            trending = await service.get_trending_recommendations(
                trending_type="hot",
                num_recommendations=5
            )
            logger.info(f"📈 Trending items: {len(trending['recommendations'])}")
            if trending['recommendations']:
                for i, item in enumerate(trending['recommendations'][:3], 1):
                    logger.info(f"  {i}. {item['title']} (trending score: {item.get('trending_score', 'N/A')})")
            
            # Test similar content
            logger.info("\n🔗 Testing Similar Content:")
            similar = await service.get_similar_content(
                content_id=1,  # Python AI article
                num_recommendations=3,
                user_id=1
            )
            logger.info(f"🎭 Similar content items: {len(similar['recommendations'])}")
            if similar['recommendations']:
                for i, item in enumerate(similar['recommendations'], 1):
                    logger.info(f"  {i}. {item['title']}")
            
            # Test feedback processing
            logger.info("\n👍 Testing Feedback Processing:")
            feedback_result = await service.record_recommendation_feedback(
                user_id=1,
                content_id=2,
                feedback_type="liked",
                algorithm="hybrid",
                recommendation_id="test_rec_123"
            )
            logger.info(f"✅ Feedback processed: {feedback_result['success']}")
            
            return results
    
    async def test_performance_analytics(self):
        """Test system performance analytics."""
        logger.info("\n📊 Testing Performance Analytics...")
        
        async with self.session_factory() as session:
            service = RecommendationService(session)
            
            # Get performance metrics
            performance = await service.get_recommendation_performance(
                algorithm=None,  # All algorithms
                days_back=30
            )
            
            logger.info(f"📈 Performance data available: {bool(performance)}")
            if performance:
                logger.info(f"🕒 Time period: {performance['time_period']}")
                logger.info(f"🧮 Algorithms tracked: {len(performance['algorithms'])}")
                logger.info(f"📋 Overall metrics available: {bool(performance['overall'])}")
    
    async def test_caching_performance(self):
        """Test caching system performance."""
        logger.info("\n⚡ Testing Cache Performance...")
        
        # Initialize cache system
        await init_cache()
        
        async with self.session_factory() as session:
            service = RecommendationService(session)
            
            # Test cache performance with multiple requests
            user_id = 1
            start_time = datetime.now()
            
            # First request (cache miss)
            rec1 = await service.get_user_recommendations(user_id=user_id, num_recommendations=5)
            first_request_time = datetime.now() - start_time
            
            start_time = datetime.now()
            # Second request (should be cached)
            rec2 = await service.get_user_recommendations(user_id=user_id, num_recommendations=5)
            second_request_time = datetime.now() - start_time
            
            logger.info(f"🕐 First request time: {first_request_time.total_seconds():.3f}s")
            logger.info(f"⚡ Second request time: {second_request_time.total_seconds():.3f}s")
            
            if second_request_time < first_request_time:
                speedup = first_request_time.total_seconds() / second_request_time.total_seconds()
                logger.info(f"🚀 Cache speedup: {speedup:.2f}x faster")
        
        await cleanup_cache()
    
    async def run_complete_test(self):
        """Run the complete production system test."""
        logger.info("🚀 Starting Production System Test")
        logger.info("=" * 60)
        
        try:
            # Setup
            await self.setup_database()
            await self.seed_sample_data()
            
            # Test all components
            await self.test_recommendation_algorithms()
            await self.test_performance_analytics()
            await self.test_caching_performance()
            
            logger.info("\n" + "=" * 60)
            logger.info("✅ Production System Test Complete!")
            logger.info("🎉 All components working successfully!")
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            raise
        finally:
            # Cleanup
            if self.engine:
                await self.engine.dispose()


async def main():
    """Run the production system test."""
    test = ProductionSystemTest()
    await test.run_complete_test()


if __name__ == "__main__":
    asyncio.run(main())