#!/bin/bash

# Development helper commands
# Usage: ./scripts/dev-commands.sh <command>

set -e

COMMAND=${1:-help}

case $COMMAND in
    "start")
        echo "🚀 Starting development environment..."
        docker-compose up -d
        echo "✅ Services started!"
        echo "API: http://localhost:8000/docs"
        ;;
    
    "stop")
        echo "🛑 Stopping development environment..."
        docker-compose down
        echo "✅ Services stopped!"
        ;;
    
    "restart")
        echo "🔄 Restarting development environment..."
        docker-compose restart
        echo "✅ Services restarted!"
        ;;
    
    "logs")
        SERVICE=${2:-""}
        if [ -z "$SERVICE" ]; then
            docker-compose logs -f
        else
            docker-compose logs -f $SERVICE
        fi
        ;;
    
    "shell")
        SERVICE=${2:-api}
        echo "🐚 Opening shell in $SERVICE container..."
        docker-compose exec $SERVICE bash
        ;;
    
    "db-shell")
        echo "🗄️  Opening PostgreSQL shell..."
        docker-compose exec db psql -U postgres -d smart_content
        ;;
    
    "redis-shell")
        echo "🔴 Opening Redis shell..."
        docker-compose exec redis redis-cli
        ;;
    
    "migrate")
        echo "📊 Running database migrations..."
        docker-compose run --rm api alembic upgrade head
        echo "✅ Migrations completed!"
        ;;
    
    "migration")
        MESSAGE=${2:-"Auto migration"}
        echo "📝 Creating new migration: $MESSAGE"
        docker-compose run --rm api alembic revision --autogenerate -m "$MESSAGE"
        echo "✅ Migration created!"
        ;;
    
    "seed")
        echo "🌱 Seeding database with sample data..."
        docker-compose run --rm api python scripts/seed_data.py
        echo "✅ Database seeded!"
        ;;
    
    "test")
        echo "🧪 Running tests..."
        docker-compose run --rm api pytest -v
        ;;
    
    "lint")
        echo "🔍 Running linting..."
        docker-compose run --rm api ruff check .
        docker-compose run --rm api black --check .
        echo "✅ Linting completed!"
        ;;
    
    "format")
        echo "✨ Formatting code..."
        docker-compose run --rm api ruff format .
        docker-compose run --rm api black .
        echo "✅ Code formatted!"
        ;;
    
    "clean")
        echo "🧹 Cleaning up Docker resources..."
        docker-compose down -v
        docker system prune -f
        echo "✅ Cleanup completed!"
        ;;
    
    "tools")
        echo "🛠️  Starting development tools..."
        docker-compose --profile tools up -d pgadmin redis-commander
        echo "✅ Tools started!"
        echo "PgAdmin: http://localhost:5050 (admin@example.com / admin)"
        echo "Redis Commander: http://localhost:8081"
        ;;
    
    "help")
        echo "Smart Content Recommendations - Development Commands"
        echo ""
        echo "Usage: ./scripts/dev-commands.sh <command>"
        echo ""
        echo "Available commands:"
        echo "  start      - Start all development services"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  logs       - View logs (add service name for specific service)"
        echo "  shell      - Open bash shell in container (default: api)"
        echo "  db-shell   - Open PostgreSQL shell"
        echo "  redis-shell- Open Redis CLI"
        echo "  migrate    - Run database migrations"
        echo "  migration  - Create new migration (add message)"
        echo "  seed       - Seed database with sample data"
        echo "  test       - Run tests"
        echo "  lint       - Run code linting"
        echo "  format     - Format code"
        echo "  clean      - Clean up Docker resources"
        echo "  tools      - Start development tools (PgAdmin, Redis Commander)"
        echo "  help       - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./scripts/dev-commands.sh start"
        echo "  ./scripts/dev-commands.sh logs api"
        echo "  ./scripts/dev-commands.sh migration 'Add user preferences'"
        ;;
    
    *)
        echo "❌ Unknown command: $COMMAND"
        echo "Run './scripts/dev-commands.sh help' for available commands"
        exit 1
        ;;
esac