# Smart Content Recommendations - Production Deployment Guide

This guide covers deploying the Smart Content Recommendations system in a production environment with Docker, PostgreSQL, and Redis.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   FastAPI App   │    │   PostgreSQL    │
│    (Nginx)      │────┤   (Multiple     │────┤   Database      │
│                 │    │    Workers)     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Redis Cache   │    │   Celery Worker │
                       │   (Session &    │    │   (Background   │
                       │    Caching)     │    │     Tasks)      │
                       └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose installed
- 4GB+ RAM available
- 20GB+ disk space
- SSL certificate for HTTPS (recommended)

## 🚀 Quick Start (Production)

### 1. Clone and Setup Environment

```bash
git clone <repository-url>
cd smart-content-recommendations

# Create production environment file
cp .env.example .env.prod
```

### 2. Configure Production Environment

Edit `.env.prod`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:your_secure_password@db:5432/smart_content
POSTGRES_PASSWORD=your_secure_password

# Redis
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=your_redis_password

# Security
SECRET_KEY=your_super_secret_key_change_this_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App Settings
DEBUG=false
API_V1_STR=/api/v1
PROJECT_NAME=Smart Content Recommendations

# Caching
REDIS_CACHE_TTL=3600
CACHE_ALGORITHM_RESULTS=true

# Recommendations
MAX_RECOMMENDATIONS_PER_REQUEST=100
ENABLE_AB_TESTING=true

# Monitoring
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

### 3. Deploy with Docker Compose

```bash
# Production deployment
docker compose -f docker-compose.prod.yml up -d

# Check services status
docker compose ps

# View logs
docker compose logs -f api
```

### 4. Initialize Database

```bash
# Run database migrations
docker compose exec api alembic upgrade head

# Optional: Load sample data
docker compose exec api python scripts/load_sample_data.py
```

## 🔧 Production Configuration

### PostgreSQL Configuration

The production setup includes optimized PostgreSQL settings:

```sql
-- postgresql.conf optimizations
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

### Redis Configuration

Production Redis configuration for optimal caching:

```
# Redis configuration
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### FastAPI Application Settings

Production application runs with:
- Multiple worker processes (4 workers)
- Async request handling
- Request/response compression
- Security headers
- Rate limiting
- CORS configuration

## 📊 Monitoring and Health Checks

### Health Check Endpoints

The application provides several health check endpoints:

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed system status
curl http://localhost:8000/health/detailed

# Database connectivity
curl http://localhost:8000/health/db

# Redis connectivity  
curl http://localhost:8000/health/cache
```

### Monitoring Stack

For production monitoring, consider adding:

```yaml
# Add to docker-compose.prod.yml
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

## 🔒 Security Considerations

### 1. Environment Variables

Never commit sensitive data to version control:

```bash
# Use Docker secrets for sensitive data
echo "your_db_password" | docker secret create db_password -
echo "your_secret_key" | docker secret create app_secret_key -
```

### 2. Network Security

```yaml
# Restrict network access
networks:
  backend:
    driver: bridge
    internal: true  # No external access
  frontend:
    driver: bridge
```

### 3. Container Security

- Non-root user in containers
- Read-only root filesystem where possible
- Resource limits configured
- Regular security updates

## 📈 Performance Optimization

### 1. Database Indexing

Critical indexes for performance:

```sql
-- User interactions (most common queries)
CREATE INDEX CONCURRENTLY idx_interactions_user_created 
ON interactions(user_id, created_at);

-- Content trending queries
CREATE INDEX CONCURRENTLY idx_content_trending_published 
ON content(trending_score DESC, is_published) 
WHERE is_published = true;

-- Category-based filtering
CREATE INDEX CONCURRENTLY idx_content_category_score 
ON content(category_id, trending_score DESC);
```

### 2. Caching Strategy

Production caching layers:

```python
# Cache configuration
CACHE_LAYERS = {
    "hot": 300,        # 5 minutes - user sessions
    "warm": 1800,      # 30 minutes - recommendations  
    "cold": 3600,      # 1 hour - content metadata
    "frozen": 86400,   # 24 hours - user profiles
}
```

### 3. Connection Pooling

Database connection optimization:

```python
# Production database settings
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 30
DATABASE_POOL_TIMEOUT = 30
DATABASE_POOL_RECYCLE = 3600
```

## 🔄 Scaling Strategies

### Horizontal Scaling

```yaml
# Scale specific services
docker compose up -d --scale api=3 --scale celery-worker=2

# Use load balancer
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### Database Read Replicas

For high-traffic scenarios:

```yaml
  db-read-replica:
    image: postgres:15-alpine
    environment:
      POSTGRES_MASTER_HOST: db
      POSTGRES_MASTER_PORT: 5432
```

## 🛠️ Maintenance Tasks

### Regular Maintenance

```bash
# Weekly tasks
docker compose exec db pg_dump smart_content > backup_$(date +%Y%m%d).sql

# Monthly tasks  
docker compose exec api python scripts/cleanup_old_interactions.py
docker compose exec redis redis-cli FLUSHDB  # Clear cache

# Update dependencies
docker compose pull
docker compose up -d --force-recreate
```

### Performance Monitoring

```bash
# Database performance
docker compose exec db psql -U postgres -d smart_content -c "
SELECT schemaname,tablename,attname,n_distinct,correlation 
FROM pg_stats WHERE tablename IN ('users','content','interactions');"

# Cache hit rates
docker compose exec redis redis-cli info stats | grep hit_rate

# Application metrics
curl http://localhost:8000/metrics
```

## 🧪 Testing Production Setup

Run the comprehensive production test:

```bash
# Test complete system
docker compose exec api python test_production_system.py

# Load testing with Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/v1/recommendations/user/1

# Test recommendation algorithms
docker compose exec api python -c "
import asyncio
from test_production_system import ProductionSystemTest
asyncio.run(ProductionSystemTest().run_complete_test())
"
```

## 📚 API Documentation

Once deployed, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🆘 Troubleshooting

### Common Issues

1. **Database Connection Refused**
   ```bash
   docker compose logs db
   # Check if PostgreSQL is fully started
   docker compose exec db pg_isready -U postgres
   ```

2. **Redis Connection Issues**
   ```bash
   docker compose logs redis
   # Test Redis connectivity
   docker compose exec redis redis-cli ping
   ```

3. **Application Startup Errors**
   ```bash
   docker compose logs api
   # Check environment variables
   docker compose exec api printenv | grep -E "(DATABASE|REDIS|SECRET)"
   ```

### Performance Issues

```bash
# Check resource usage
docker stats

# Analyze slow queries
docker compose exec db psql -U postgres -d smart_content -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC LIMIT 10;"
```

## 🎯 Success Metrics

After deployment, monitor these key metrics:

- **Response Times**: < 200ms for cached requests, < 1s for complex queries
- **Cache Hit Rate**: > 80% for recommendation requests  
- **Database Connections**: < 80% of pool size
- **Memory Usage**: < 80% of allocated resources
- **Error Rate**: < 1% of total requests

---

## 🎉 Congratulations!

Your Smart Content Recommendations system is now running in production! 

The system provides:
- ✅ Scalable recommendation algorithms
- ✅ High-performance caching
- ✅ Production-ready database setup
- ✅ Comprehensive monitoring
- ✅ Professional testing suite

For support or questions, refer to the API documentation or check the application logs.
