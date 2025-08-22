-- Database initialization script
-- This runs automatically when PostgreSQL container starts for the first time

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Set timezone
SET timezone = 'UTC';

-- Create indexes for better performance (will be created by Alembic migrations)
-- This is just for reference

COMMENT ON DATABASE smart_content IS 'Smart Content Recommendations Platform Database';