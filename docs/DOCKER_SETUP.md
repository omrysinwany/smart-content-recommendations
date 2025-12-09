# 🐳 Docker Setup Guide - Smart Content Recommendations

## For When Docker is Available

This guide shows you how to run the complete system with Docker and all production features.

## 🚀 Quick Start with Docker

### Option 1: Development Mode

```bash
# 1. Start all services
export PATH="$HOME/.local/bin:$PATH"
docker-compose up -d

# 2. Check services are running
docker-compose ps

# 3. Run database migrations
docker-compose exec api pipenv run alembic upgrade head

# 4. Access the application
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# PgAdmin: http://localhost:5050 (admin@example.com / admin)
# Redis Commander: http://localhost:8081
```

### Option 2: Production Mode

```bash
# 1. Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/smart_content"
export REDIS_URL="redis://localhost:6379"
export SECRET_KEY="your-super-secret-production-key"

# 2. Start production services
docker-compose -f docker-compose.prod.yml up -d

# 3. Production app runs on port 80 with Nginx
curl http://localhost/health
```

## 🔧 Available Services

| Service | Port | Purpose |
|---------|------|---------|
| **API** | 8000 | FastAPI application |
| **Database** | 5432 | PostgreSQL database |
| **Redis** | 6379 | Caching and Celery |
| **PgAdmin** | 5050 | Database management |
| **Redis Commander** | 8081 | Redis management |
| **Celery Worker** | - | Background tasks |
| **Celery Beat** | - | Scheduled tasks |

## 📊 Development Tools

### Start with admin tools
```bash
# Start with database admin tools
docker-compose --profile tools up -d
```

### View logs
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f db
```

### Execute commands
```bash
# Run database migrations
docker-compose exec api pipenv run alembic upgrade head

# Run tests
docker-compose exec api pipenv run pytest

# Shell into API container
docker-compose exec api bash

# Database shell
docker-compose exec db psql -U postgres -d smart_content
```

## 🧪 Test the Full System

### 1. API Tests
```bash
# Test all endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/recommendations/trending
curl http://localhost:8000/docs  # Interactive docs
```

### 2. Load Testing
```bash
# Install locust in the container
docker-compose exec api pip install locust

# Run load tests
docker-compose exec api locust -f tests/load_test.py --host=http://localhost:8000
```

### 3. Database Operations
```bash
# Connect to database
docker-compose exec db psql -U postgres -d smart_content

# Run SQL queries
SELECT COUNT(*) FROM users;
SELECT title, view_count FROM contents ORDER BY view_count DESC LIMIT 5;
```

## 🚀 Production Deployment

### Environment Variables
Create a `.env.prod` file:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@prod-db:5432/smart_content
REDIS_URL=redis://prod-redis:6379
SECRET_KEY=your-super-secret-production-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
S3_BUCKET_NAME=your-bucket
SENTRY_DSN=your-sentry-dsn
```

### Deploy to Production
```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Deploy with scaling
docker-compose -f docker-compose.prod.yml up -d --scale api=3 --scale celery-worker=2

# Health checks
curl http://your-domain.com/health
```

## 🔍 Monitoring

### Service Health
```bash
# Check service status
docker-compose ps

# View resource usage
docker stats

# Check logs for errors
docker-compose logs --tail=100 api | grep ERROR
```

### Application Metrics
- **Health**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/docs
- **Database Admin**: http://localhost:5050
- **Redis Admin**: http://localhost:8081

## 🛠️ Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Find what's using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

**Database connection issues:**
```bash
# Check database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Reset database
docker-compose down -v
docker-compose up -d db
```

**Permission issues:**
```bash
# Fix permissions
sudo chown -R $USER:$USER .
```

### Reset Everything
```bash
# Complete cleanup
docker-compose down -v --remove-orphans
docker system prune -a
docker-compose up -d
```

## 🎯 Development Workflow

### 1. Start Development
```bash
docker-compose up -d
docker-compose logs -f api
```

### 2. Make Changes
- Edit code (auto-reloads with volume mounts)
- Run tests: `docker-compose exec api pipenv run pytest`
- Check logs: `docker-compose logs -f api`

### 3. Database Changes
```bash
# Create migration
docker-compose exec api pipenv run alembic revision --autogenerate -m "description"

# Apply migration
docker-compose exec api pipenv run alembic upgrade head
```

### 4. Production Deploy
```bash
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## 🏆 Full System Features

When running with Docker, you get:

✅ **Complete FastAPI application** with all endpoints  
✅ **PostgreSQL database** with real data persistence  
✅ **Redis caching** with multi-level TTL strategy  
✅ **Celery background tasks** for heavy operations  
✅ **Database migrations** with Alembic  
✅ **Admin interfaces** for database and Redis  
✅ **Production-ready** with Nginx reverse proxy  
✅ **Monitoring** with health checks and metrics  
✅ **Scalability** with container orchestration  
✅ **CI/CD integration** with GitHub Actions  

This demonstrates **enterprise-level** system architecture and deployment practices!
