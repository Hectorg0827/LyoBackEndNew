"""
Health check router.

This module defines the health check endpoints for the application
and its dependencies.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Response, status

from api.core.config import settings
from api.core.logging import get_logger
from api.db.firestore import get_firestore
from api.db.redis import get_redis
from api.db.sql import get_db
from api.services.user import UserService

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic health check")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns basic information about the API status.
    
    Returns:
        Dict: Health status information
    """
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "service": settings.APP_NAME,
    }


@router.get("/health/live", summary="Liveness probe")
async def liveness_probe() -> Dict[str, str]:
    """
    Liveness probe endpoint.
    
    Kubernetes uses this to determine if the pod should be restarted.
    
    Returns:
        Dict: Health status
    """
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def readiness_probe(
    response: Response,
    db=Depends(get_db),
    redis=Depends(get_redis),
    firestore=Depends(get_firestore),
    user_service: UserService = Depends(),
) -> Dict[str, Any]:
    """
    Readiness probe endpoint.
    
    Checks if the service is ready to handle requests by verifying connectivity
    to all dependencies.
    
    Args:
        response: FastAPI Response object
        db: Database session
        redis: Redis client
        firestore: Firestore client
        user_service: User service
        
    Returns:
        Dict: Health status with details for each dependency
    """
    is_healthy = True
    checks: List[Dict[str, Any]] = []
    
    # Check database
    try:
        # Simple query to test database connection
        db.execute("SELECT 1")
        checks.append({
            "name": "database",
            "status": "ok"
        })
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        is_healthy = False
        checks.append({
            "name": "database",
            "status": "error",
            "message": str(e) if settings.DEBUG else "Database connection failed"
        })
    
    # Check Redis
    try:
        await redis.ping()
        checks.append({
            "name": "redis",
            "status": "ok"
        })
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        is_healthy = False
        checks.append({
            "name": "redis",
            "status": "error",
            "message": str(e) if settings.DEBUG else "Redis connection failed"
        })
    
    # Check Firestore
    try:
        # Simple check to verify Firestore connection
        firestore_status = firestore._client is not None
        if firestore_status:
            checks.append({
                "name": "firestore",
                "status": "ok"
            })
        else:
            raise Exception("Firestore client not initialized")
    except Exception as e:
        logger.error(f"Firestore health check failed: {str(e)}")
        is_healthy = False
        checks.append({
            "name": "firestore",
            "status": "error",
            "message": str(e) if settings.DEBUG else "Firestore connection failed"
        })
    
    # Set response status based on health
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return {
        "status": "ok" if is_healthy else "error",
        "version": "1.0.0",
        "checks": checks
    }


@router.get("/health/deep", summary="Deep health check")
async def deep_health_check(
    response: Response,
    db=Depends(get_db),
    redis=Depends(get_redis),
    firestore=Depends(get_firestore),
    user_service: UserService = Depends(),
) -> Dict[str, Any]:
    """
    Deep health check endpoint.
    
    Performs in-depth checks of all dependencies and functionalities.
    
    Args:
        response: FastAPI Response object
        db: Database session
        redis: Redis client
        firestore: Firestore client
        user_service: User service
        
    Returns:
        Dict: Detailed health status information
    """
    is_healthy = True
    checks = []
    
    # Check database
    try:
        # Simple query to test database connection
        db.execute("SELECT 1")
        checks.append({
            "name": "database",
            "status": "ok",
            "details": {
                "type": "postgres",
                "host": settings.POSTGRES_SERVER,
                "database": settings.POSTGRES_DB,
            }
        })
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        is_healthy = False
        checks.append({
            "name": "database",
            "status": "error",
            "message": str(e) if settings.DEBUG else "Database connection failed",
            "details": {
                "type": "postgres",
                "host": settings.POSTGRES_SERVER,
                "database": settings.POSTGRES_DB,
            }
        })
    
    # Check Redis
    try:
        # Get Redis info
        info = await redis.info()
        checks.append({
            "name": "redis",
            "status": "ok",
            "details": {
                "version": info.get("redis_version", "unknown"),
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "used_memory": info.get("used_memory_human", "unknown"),
                "clients_connected": info.get("connected_clients", "unknown"),
            }
        })
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        is_healthy = False
        checks.append({
            "name": "redis",
            "status": "error",
            "message": str(e) if settings.DEBUG else "Redis connection failed",
            "details": {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
            }
        })
    
    # Check Firestore
    try:
        # Get a data point to test Firestore connection
        test_ref = firestore._client.collection("_healthcheck").document("test")
        await test_ref.set({"timestamp": firestore.field_server_timestamp()})
        await test_ref.delete()
        
        checks.append({
            "name": "firestore",
            "status": "ok",
            "details": {
                "project_id": settings.FIRESTORE_PROJECT_ID or "emulator",
            }
        })
    except Exception as e:
        logger.error(f"Firestore health check failed: {str(e)}")
        is_healthy = False
        checks.append({
            "name": "firestore",
            "status": "error",
            "message": str(e) if settings.DEBUG else "Firestore connection failed",
            "details": {
                "project_id": settings.FIRESTORE_PROJECT_ID or "emulator",
            }
        })
    
    # Set response status based on health
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Include system info
    import platform
    import psutil
    
    system_info = {
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "memory_usage": psutil.virtual_memory().percent,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    
    return {
        "status": "ok" if is_healthy else "error",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
        "system": system_info,
    }
