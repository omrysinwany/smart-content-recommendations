#!/bin/bash
# Database backup script for Smart Content Recommendations

set -e

# Configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME=${POSTGRES_DB:-smart_content}
DB_USER=${POSTGRES_USER:-postgres}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup filename
BACKUP_FILE="$BACKUP_DIR/smart_content_backup_$TIMESTAMP.sql"

echo "Starting database backup..."
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT"
echo "User: $DB_USER"
echo "Backup file: $BACKUP_FILE"

# Create the backup
PGPASSWORD=$POSTGRES_PASSWORD pg_dump \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --verbose \
  --no-password \
  --format=custom \
  --compress=9 \
  --file="$BACKUP_FILE"

# Compress the backup
gzip "$BACKUP_FILE"
COMPRESSED_FILE="$BACKUP_FILE.gz"

echo "Backup completed: $COMPRESSED_FILE"

# Optional: Upload to cloud storage (uncomment and configure as needed)
# aws s3 cp "$COMPRESSED_FILE" s3://your-backup-bucket/database/
# gsutil cp "$COMPRESSED_FILE" gs://your-backup-bucket/database/

# Optional: Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "smart_content_backup_*.sql.gz" -mtime +7 -delete

echo "Backup process completed successfully"