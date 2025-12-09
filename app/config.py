import os
from typing import Optional

import boto3
from botocore.exceptions import NoCredentialsError
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application configuration using Pydantic Settings.

    Enhanced for AWS deployment with:
    1. AWS service integrations (RDS, ElastiCache, S3)
    2. AWS Secrets Manager support
    3. CloudWatch logging configuration
    4. ECS/EKS deployment settings
    """

    # Application
    app_name: str = "Smart Content Recommendations"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # Database - AWS RDS
    database_url: str = "postgresql+asyncpg://postgres:password@localhost/smart_content"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_ssl_mode: str = "prefer"  # For RDS SSL connections

    # Redis - AWS ElastiCache
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 3600  # 1 hour in seconds
    redis_ssl: bool = False  # Enable for ElastiCache with encryption

    # Authentication & Security
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # AWS Configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    aws_profile: Optional[str] = None

    # AWS S3 Storage
    s3_bucket_name: Optional[str] = None
    s3_endpoint_url: Optional[str] = None  # For LocalStack testing
    s3_use_ssl: bool = True

    # AWS Secrets Manager
    use_aws_secrets: bool = False
    aws_secret_name: Optional[str] = None

    # AWS CloudWatch Logging
    cloudwatch_log_group: str = "/aws/ecs/smart-content-recommendations"
    cloudwatch_log_stream: Optional[str] = None

    # AWS Application Load Balancer Health Checks
    health_check_path: str = "/health"
    health_check_interval: int = 30

    # Celery (Background Jobs) - Compatible with AWS ElastiCache
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
        extra = "allow"  # Allow extra fields from .env

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.use_aws_secrets and self.environment == "production":
            self._load_aws_secrets()

    def _load_aws_secrets(self):
        """Load sensitive configuration from AWS Secrets Manager."""
        if not self.aws_secret_name:
            return

        try:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region,
            )

            secrets_client = session.client("secretsmanager")
            response = secrets_client.get_secret_value(SecretId=self.aws_secret_name)

            import json

            secrets = json.loads(response["SecretString"])

            # Update sensitive settings from secrets
            if "database_url" in secrets:
                self.database_url = secrets["database_url"]
            if "secret_key" in secrets:
                self.secret_key = secrets["secret_key"]
            if "redis_url" in secrets:
                self.redis_url = secrets["redis_url"]
            if "celery_broker_url" in secrets:
                self.celery_broker_url = secrets["celery_broker_url"]
            if "celery_result_backend" in secrets:
                self.celery_result_backend = secrets["celery_result_backend"]

        except Exception as e:
            print(f"Warning: Could not load AWS secrets: {e}")

    def get_s3_client(self):
        """Get configured S3 client."""
        try:
            return boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region,
                endpoint_url=self.s3_endpoint_url,
                use_ssl=self.s3_use_ssl,
            )
        except NoCredentialsError:
            print("Warning: AWS credentials not found for S3")
            return None

    def get_cloudwatch_client(self):
        """Get configured CloudWatch Logs client."""
        try:
            return boto3.client(
                "logs",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region,
            )
        except NoCredentialsError:
            print("Warning: AWS credentials not found for CloudWatch")
            return None

    @property
    def is_aws_environment(self) -> bool:
        """Check if running in AWS environment."""
        return (
            self.environment in ["staging", "production"]
            and self.aws_region is not None
        )

    @property
    def database_url_with_ssl(self) -> str:
        """Get database URL with SSL configuration for AWS RDS."""
        if self.is_aws_environment and "sslmode=" not in self.database_url:
            separator = "&" if "?" in self.database_url else "?"
            return f"{self.database_url}{separator}sslmode={self.database_ssl_mode}"
        return self.database_url


# Global settings instance
settings = Settings()
