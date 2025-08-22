from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
from contextlib import asynccontextmanager

from app.config import settings
from app.api.v1.api import api_router
# from app.database import init_db  # We'll uncomment when we set up Alembic


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    
    This replaces the old startup/shutdown event handlers and provides:
    1. Clean resource management
    2. Database connection pool initialization
    3. Background task startup/cleanup
    """
    # Startup
    print("🚀 Starting Smart Content Recommendations API")
    
    # Initialize database
    # await init_db()
    
    # Start background services
    print("✅ Application startup complete")
    
    yield
    
    # Shutdown
    print("🔄 Shutting down application")
    # Clean up resources here
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
                "detail": str(exc) if settings.debug else "Something went wrong"
            }
        )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": "development" if settings.debug else "production"
        }
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": f"Welcome to {settings.app_name}!",
            "docs_url": "/docs",
            "version": settings.app_version
        }
    
    # Include API routers
    app.include_router(api_router, prefix="/api")
    
    return app


# Create the application instance
app = create_app()