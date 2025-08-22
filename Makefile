# Smart Content Recommendations - Development Makefile
# This provides easy commands for common development tasks

.PHONY: help setup start stop restart logs shell db-shell redis-shell migrate migration seed test lint format clean tools

# Default target
help:
	@echo "Smart Content Recommendations - Development Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make setup     - Initial development environment setup"
	@echo ""
	@echo "Service Management:"
	@echo "  make start     - Start all services"
	@echo "  make stop      - Stop all services"
	@echo "  make restart   - Restart all services"
	@echo "  make logs      - View all service logs"
	@echo ""
	@echo "Development:"
	@echo "  make shell     - Open shell in API container"
	@echo "  make db-shell  - Open PostgreSQL shell"
	@echo "  make redis-shell - Open Redis shell"
	@echo ""
	@echo "Database:"
	@echo "  make migrate   - Run database migrations"
	@echo "  make migration MSG='message' - Create new migration"
	@echo "  make seed      - Seed database with sample data"
	@echo ""
	@echo "Code Quality:"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run linting"
	@echo "  make format    - Format code"
	@echo ""
	@echo "Utilities:"
	@echo "  make tools     - Start development tools (PgAdmin, Redis Commander)"
	@echo "  make clean     - Clean up Docker resources"

# Initial setup
setup:
	@echo "🚀 Setting up development environment..."
	@./scripts/dev-setup.sh

# Service management
start:
	@echo "🚀 Starting development environment..."
	@docker-compose up -d
	@echo "✅ Services started!"
	@echo "API Documentation: http://localhost:8000/docs"
	@echo "Health Check: http://localhost:8000/health"

stop:
	@echo "🛑 Stopping services..."
	@docker-compose down
	@echo "✅ Services stopped!"

restart:
	@echo "🔄 Restarting services..."
	@docker-compose restart
	@echo "✅ Services restarted!"

logs:
	@docker-compose logs -f

# Development shells
shell:
	@echo "🐚 Opening API container shell..."
	@docker-compose exec api bash

db-shell:
	@echo "🗄️  Opening PostgreSQL shell..."
	@docker-compose exec db psql -U postgres -d smart_content

redis-shell:
	@echo "🔴 Opening Redis shell..."
	@docker-compose exec redis redis-cli

# Database operations
migrate:
	@echo "📊 Running database migrations..."
	@docker-compose run --rm api alembic upgrade head
	@echo "✅ Migrations completed!"

migration:
	@echo "📝 Creating migration: $(MSG)"
	@docker-compose run --rm api alembic revision --autogenerate -m "$(MSG)"
	@echo "✅ Migration created!"

seed:
	@echo "🌱 Seeding database with sample data..."
	@docker-compose run --rm api python scripts/seed_data.py
	@echo "✅ Database seeded!"

# Code quality
test:
	@echo "🧪 Running tests..."
	@docker-compose run --rm api pytest -v --cov=app --cov-report=html
	@echo "✅ Tests completed! Coverage report: htmlcov/index.html"

lint:
	@echo "🔍 Running linting..."
	@docker-compose run --rm api ruff check app/
	@docker-compose run --rm api mypy app/
	@echo "✅ Linting completed!"

format:
	@echo "✨ Formatting code..."
	@docker-compose run --rm api ruff format app/
	@docker-compose run --rm api ruff check --fix app/
	@echo "✅ Code formatted!"

# Development tools
tools:
	@echo "🛠️  Starting development tools..."
	@docker-compose --profile tools up -d pgadmin redis-commander
	@echo "✅ Development tools started!"
	@echo ""
	@echo "Available tools:"
	@echo "  PgAdmin: http://localhost:5050"
	@echo "    Email: admin@example.com"
	@echo "    Password: admin"
	@echo ""
	@echo "  Redis Commander: http://localhost:8081"

# Cleanup
clean:
	@echo "🧹 Cleaning up Docker resources..."
	@docker-compose down -v --remove-orphans
	@docker system prune -f
	@echo "✅ Cleanup completed!"

# Production commands
build-prod:
	@echo "🏭 Building production images..."
	@docker-compose -f docker-compose.prod.yml build
	@echo "✅ Production images built!"

deploy-prod:
	@echo "🚀 Deploying to production..."
	@docker-compose -f docker-compose.prod.yml up -d
	@echo "✅ Production deployment completed!"

# Status check
status:
	@echo "📊 Service Status:"
	@docker-compose ps
	@echo ""
	@echo "🔍 Health Checks:"
	@curl -s http://localhost:8000/health | jq . || echo "API not responding"