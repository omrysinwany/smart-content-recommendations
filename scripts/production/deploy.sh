#!/bin/bash
# Production deployment script for Smart Content Recommendations

set -e

echo "🚀 Starting deployment of Smart Content Recommendations..."

# Configuration
PROJECT_DIR="/opt/smart-content-recommendations"
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root or with sudo"
   exit 1
fi

# Backup current deployment
print_status "Creating backup of current deployment..."
if [ -d "$PROJECT_DIR" ]; then
    tar -czf "$BACKUP_DIR/deployment_backup_$TIMESTAMP.tar.gz" -C "$PROJECT_DIR" .
    print_status "Backup created: $BACKUP_DIR/deployment_backup_$TIMESTAMP.tar.gz"
fi

# Pull latest code (assuming git deployment)
print_status "Pulling latest code..."
cd "$PROJECT_DIR"
git fetch origin
git checkout main
git pull origin main

# Build new Docker images
print_status "Building Docker images..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Run database migrations
print_status "Running database migrations..."
docker-compose -f docker-compose.prod.yml run --rm app alembic upgrade head

# Stop old containers
print_status "Stopping old containers..."
docker-compose -f docker-compose.prod.yml down

# Start new containers
print_status "Starting new containers..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 30

# Health check
print_status "Performing health check..."
if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    print_status "✅ Health check passed"
else
    print_error "❌ Health check failed"
    
    # Rollback on failure
    print_warning "Rolling back to previous deployment..."
    docker-compose -f docker-compose.prod.yml down
    
    # Restore from backup if it exists
    if [ -f "$BACKUP_DIR/deployment_backup_$TIMESTAMP.tar.gz" ]; then
        rm -rf "$PROJECT_DIR"/*
        tar -xzf "$BACKUP_DIR/deployment_backup_$TIMESTAMP.tar.gz" -C "$PROJECT_DIR"
        docker-compose -f docker-compose.prod.yml up -d
    fi
    
    exit 1
fi

# Clean up old Docker images
print_status "Cleaning up old Docker images..."
docker image prune -f

# Clean up old backups (keep last 5)
find "$BACKUP_DIR" -name "deployment_backup_*.tar.gz" | sort -r | tail -n +6 | xargs -r rm

print_status "🎉 Deployment completed successfully!"
print_status "Application is running at: http://localhost:8000"