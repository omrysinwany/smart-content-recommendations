#!/usr/bin/env python3
"""
Local development runner - Alternative to Docker for quick testing.

This demonstrates the application structure without requiring Docker.
In production, you'd use the Docker setup instead.
"""

import asyncio
import uvicorn
from app.main import app

def main():
    """Run the application locally"""
    print("🚀 Starting Smart Content Recommendations API")
    print("📝 Note: This is local mode - database features will be limited")
    print("🐳 For full features, use: docker-compose up")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    print("-" * 50)
    
    # Run the server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )

if __name__ == "__main__":
    main()