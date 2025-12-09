#!/bin/bash

# Development setup script
# This script helps set up the development environment

set -e

echo "🚀 Setting up Smart Content Recommendations development environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
    echo "✅ .env file created. Please review and update if needed."
fi

# Build and start services
echo "🔨 Building Docker containers..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d db redis

echo "⏳ Waiting for database to be ready..."
timeout 60 bash -c 'until docker-compose exec -T db pg_isready -U postgres -d smart_content; do sleep 2; done'

echo "📊 Running database migrations..."
docker-compose run --rm api alembic upgrade head

echo "🌱 Seeding database with sample data..."
docker-compose run --rm api python -c "
import asyncio
from app.database import init_db
asyncio.run(init_db())
print('Database initialized!')
"

echo "🎉 Development environment is ready!"
echo ""
echo "Available services:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Database: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "To start all services: docker-compose up"
echo "To view logs: docker-compose logs -f"
echo "To stop services: docker-compose down"