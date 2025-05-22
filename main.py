"""
Main application module for Lyo backend.

This module initializes the FastAPI application and includes all routers.
"""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import settings
from api.core.docs import setup_api_docs
from api.core.errors import setup_error_handlers
from api.core.logging import setup_logging
from api.core.telemetry import setup_telemetry
from api.db.redis import initialize_redis, redis_client
from api.db.sql import init_db
from api.middlewares import RequestIDMiddleware
from api.middlewares.rate_limit import setup_rate_limiting
from api.routers import (
    ads,
    ai,
    auth,
    content,
    feed,
    health,
    notifications,
    user,
)

# Initialize logging
setup_logging()

# Initialize OpenTelemetry
setup_telemetry()

# Create FastAPI application
app = FastAPI(
    title="Lyo API",
    description="Backend API for Lyo, an AI-powered, multilingual social-learning app",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# Set up API documentation
setup_api_docs(app)

# Set up error handlers
setup_error_handlers(app)

# Add request ID middleware (should be first to ensure all requests have an ID)
app.add_middleware(RequestIDMiddleware)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with version prefix
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(user.router, prefix="/api/v1", tags=["User"])
app.include_router(feed.router, prefix="/api/v1", tags=["Feed"])
app.include_router(content.router, prefix="/api/v1", tags=["Content"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(ai.router, prefix="/api/v1", tags=["AI"])
app.include_router(ads.router, prefix="/api/v1", tags=["Ads"])


@app.on_event("startup")
async def startup_event():
    """
    Run startup events.
    
    Initialize connections and services when the application starts.
    """
    # Initialize database
    await init_db()
    
    # Initialize Redis
    await initialize_redis()
    
    # Setup rate limiting middleware
    if redis_client is not None:
        await setup_rate_limiting(app, redis_client)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Run shutdown events.
    
    Clean up connections and resources when the application shuts down.
    """
    # Close Redis connection
    if redis_client is not None:
        await redis_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )
