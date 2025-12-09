import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.config import settings

# from app.database import init_db  # We'll uncomment when we set up Alembic


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events with AWS service initialization.

    This handles:
    1. Database connection pool initialization
    2. Redis/ElastiCache connection
    3. S3 storage service initialization
    4. AWS secrets loading
    5. Background task startup/cleanup
    """
    # Startup
    print(
        f"🚀 Starting Smart Content Recommendations API (Environment: {settings.environment})"
    )

    # Initialize AWS services first (if in AWS environment)
    if settings.is_aws_environment:
        print("🔧 Initializing AWS services...")
        try:
            # Initialize S3 storage
            from app.core.storage import init_storage

            await init_storage()

            # Initialize CloudWatch logging if configured
            if settings.cloudwatch_log_group:
                print(f"📝 CloudWatch logging enabled: {settings.cloudwatch_log_group}")

            print("✅ AWS services initialized successfully")
        except Exception as e:
            print(f"⚠️ AWS services initialization failed: {e}")
            # Continue startup - app can run without some AWS services

    # Initialize database
    try:
        from app.database import engine

        # Test database connection
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT 1")
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise

    # Initialize Redis/ElastiCache
    try:
        from app.core.cache import init_cache

        await init_cache()
        print("✅ Cache system initialized")
    except Exception as e:
        print(f"⚠️ Cache initialization failed: {e}")
        # Continue - app can run without cache

    # Initialize database tables (uncomment when Alembic is set up)
    # from app.database import init_db
    # await init_db()

    print("✅ Application startup complete")

    yield

    # Shutdown
    print("🔄 Shutting down application")

    # Clean up AWS services
    if settings.is_aws_environment:
        print("🔧 Cleaning up AWS services...")

    # Clean up cache connections
    try:
        from app.core.cache import cleanup_cache

        await cleanup_cache()
        print("✅ Cache connections closed")
    except Exception as e:
        print(f"⚠️ Cache cleanup error: {e}")

    # Clean up database connections
    try:
        from app.database import engine

        await engine.dispose()
        print("✅ Database connections closed")
    except Exception as e:
        print(f"⚠️ Database cleanup error: {e}")

    print("✅ Application shutdown complete")


def create_app() -> FastAPI:
    """
    Application factory pattern.

    Benefits:
    1. Easy testing with different configurations
    2. Multiple app instances possible
    3. Clear initialization flow
    4. Environment-specific setup
    """

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="A production-ready content recommendation platform",
        docs_url="/docs" if settings.debug else None,  # Hide docs in production
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware for tracing
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        return response

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "request_id": getattr(request.state, "request_id", None),
                "detail": str(exc) if settings.debug else "Something went wrong",
            },
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        health_status = {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "timestamp": time.time(),
        }

        # Add AWS-specific health checks
        if settings.is_aws_environment:
            health_status["aws"] = {
                "region": settings.aws_region,
                "s3_configured": bool(settings.s3_bucket_name),
                "secrets_manager": settings.use_aws_secrets,
                "cloudwatch_logs": bool(settings.cloudwatch_log_group),
            }

        return health_status

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": f"Welcome to {settings.app_name}!",
            "docs_url": "/docs",
            "version": settings.app_version,
        }

    # Include API routers
    app.include_router(api_router, prefix="/api")

    return app


# Create the application instance
app = create_app()
