from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application configuration using Pydantic Settings.
    
    This approach provides:
    1. Type validation for all config values
    2. Automatic environment variable loading
    3. Default values with clear documentation
    4. IDE autocompletion for configuration
    """
    
    # Application
    app_name: str = "Smart Content Recommendations"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost/smart_content"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 3600  # 1 hour in seconds
    
    # Authentication
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # AWS Configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket_name: Optional[str] = None
    
    # Celery (Background Jobs)
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # Recommendation Engine
    recommendation_batch_size: int = 100
    min_interactions_for_recommendations: int = 5
    
    # Performance Settings
    api_rate_limit: int = 1000  # requests per minute
    max_content_per_page: int = 50
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()