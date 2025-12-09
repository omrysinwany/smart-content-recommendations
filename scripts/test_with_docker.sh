#!/bin/bash

# Test Content & Recommendations using Docker
# This runs inside your existing container with all dependencies

echo "🚀 Testing Content & Recommendations via Docker"
echo "==============================================="

# Check if containers are running
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Containers not running. Starting them..."
    docker-compose up -d
    sleep 10
fi

echo "📊 CONTENT OVERVIEW:"
echo "-------------------"

# Get content via Docker
docker-compose exec -T app python -c "
import asyncio
import sys
import os
sys.path.append('/app')

from app.database import get_db
from app.repositories.content_repository import ContentRepository

async def show_content():
    async for db in get_db():
        repo = ContentRepository(db)
        content_list = await repo.get_all(limit=10)
        
        print(f'📚 Found {len(content_list)} content items:')
        print()
        
        for i, content in enumerate(content_list, 1):
            print(f'{i}. [{content.id}] {content.title}')
            print(f'   Type: {content.content_type.value} | Category: {content.category.name if content.category else \"None\"}')
            if content.description:
                print(f'   Description: {content.description[:100]}...')
            print(f'   Stats: {content.view_count} views, {content.like_count} likes')
            print()
        break

asyncio.run(show_content())
"

echo
echo "🎯 RECOMMENDATION TESTING:"
echo "-------------------------"

# Test recommendations via Docker
docker-compose exec -T app python -c "
import asyncio
import sys
import os
sys.path.append('/app')

from app.database import get_db
from app.services.recommendation_service import RecommendationService
from app.repositories.user_repository import UserRepository

async def test_recommendations():
    async for db in get_db():
        # Get or create a test user
        user_repo = UserRepository(db)
        users = await user_repo.get_all(limit=1)
        
        if not users:
            print('❌ No users found. Creating test user...')
            from app.models.user import User
            from app.core.security import get_password_hash
            
            test_user = User(
                email='test@example.com',
                username='testuser',
                full_name='Test User',
                hashed_password=get_password_hash('testpass123'),
                is_active=True,
                is_verified=True
            )
            
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)
            user_id = test_user.id
            print(f'✅ Created test user with ID: {user_id}')
        else:
            user_id = users[0].id
            print(f'✅ Using existing user ID: {user_id}')
        
        # Test different algorithms
        service = RecommendationService(db)
        algorithms = ['trending_hot', 'content_based', 'hybrid', 'auto']
        
        for algorithm in algorithms:
            try:
                print(f'\\n🤖 Testing {algorithm.upper()} algorithm:')
                result = await service.get_user_recommendations(
                    user_id=user_id,
                    algorithm=algorithm,
                    num_recommendations=3
                )
                
                recommendations = result.get('recommendations', [])
                if recommendations:
                    for i, rec in enumerate(recommendations, 1):
                        print(f'   {i}. {rec[\"title\"]} (Score: {rec.get(\"score\", 0):.3f})')
                        if 'explanation' in rec:
                            exp = rec['explanation']
                            print(f'      Reason: {exp.get(\"reason\", \"No reason\")}')
                            factors = exp.get('factors', [])
                            if factors:
                                print(f'      Factor: {factors[0]}')
                else:
                    print('   📭 No recommendations found')
                
                # Show algorithm info
                if 'algorithm_info' in result:
                    info = result['algorithm_info']
                    print(f'   📊 {info.get(\"explanation\", \"No explanation\")}')
                    
            except Exception as e:
                print(f'   ❌ Error with {algorithm}: {str(e)[:100]}...')
        
        break

asyncio.run(test_recommendations())
"

echo
echo "==============================================="
echo "✅ Docker testing completed!"
echo
echo "💡 Next steps:"
echo "1. To create interactions: Use POST /api/v1/content/{id}/interact"
echo "2. To test specific content: Use GET /api/v1/content/{id}" 
echo "3. For UI-like experience: Install 'pip install httpx rich' and run 'python3 scripts/inspect_content.py'"
