"""
Error handling utilities for AI components.

This module provides utility functions for handling errors in AI-driven features.
"""
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from api.core.errors_ai import (
    AIQuotaExceededError,
    AlgorithmError,
    ContentModerationError, 
    DataProcessingError,
    ModelExecutionError,
    RecommendationError,
)

# Type variable for function return type
T = TypeVar("T")

logger = logging.getLogger(__name__)


async def handle_ai_error(request: Request, response: Response, error: Exception) -> Dict[str, Any]:
    """
    Handle AI-specific errors and log detailed information.
    
    Args:
        request: FastAPI request
        response: FastAPI response
        error: Exception that occurred
    
    Returns:
        Dict with error details for logging
    """
    # Extract relevant request information for logging
    user_id = getattr(request.state, "user_id", None)
    session_id = request.cookies.get("session_id")
    user_agent = request.headers.get("User-Agent")
    
    # Build error context for logging
    error_context = {
        "user_id": user_id,
        "session_id": session_id,
        "user_agent": user_agent,
        "path": request.url.path,
        "method": request.method,
        "error_type": error.__class__.__name__,
        "error_message": str(error),
    }
    
    # Log error with context
    if isinstance(error, (AlgorithmError, ModelExecutionError)):
        logger.error(
            f"AI algorithm error: {error}",
            extra=error_context
        )
    elif isinstance(error, DataProcessingError):
        logger.error(
            f"Data processing error: {error}",
            extra=error_context
        )
    elif isinstance(error, AIQuotaExceededError):
        logger.warning(
            f"AI quota exceeded: {error}",
            extra=error_context
        )
    else:
        logger.error(
            f"Unhandled AI error: {error}",
            extra=error_context
        )
    
    return error_context


def handle_ai_errors(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to handle AI-specific errors.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await func(*args, **kwargs)
        except RecommendationError as e:
            # Get request and response objects if available
            request = next((arg for arg in args if isinstance(arg, Request)), None)
            response = kwargs.get("response")
            
            if request:
                await handle_ai_error(request, response, e)
            
            # Re-raise the error to be handled by the global error handler
            raise
        except ModelExecutionError as e:
            # Log model errors with more details
            logger.error(
                f"Model execution error: {e}",
                extra={
                    "model_name": getattr(e, "data", {}).get("model_name"),
                    "error_type": getattr(e, "data", {}).get("error_type"),
                }
            )
            raise
        except Exception as e:
            # Unexpected errors
            logger.exception(f"Unexpected error in AI component: {e}")
            raise
    
    return cast(Callable[..., T], wrapper)


def graceful_ai_degradation(
    fallback_value: Any, 
    log_error: bool = True,
    error_types: List[type] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to gracefully degrade AI features when errors occur.
    
    Args:
        fallback_value: Value to return when an error occurs
        log_error: Whether to log the error
        error_types: List of error types to catch
        
    Returns:
        Decorated function
    """
    if error_types is None:
        error_types = [
            AlgorithmError, 
            ModelExecutionError, 
            DataProcessingError, 
            ContentModerationError,
            AIQuotaExceededError,
        ]
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except tuple(error_types) as e:
                if log_error:
                    # Get request object if available
                    request = next((arg for arg in args if isinstance(arg, Request)), None)
                    if request:
                        await handle_ai_error(request, None, e)
                    else:
                        logger.error(f"AI error (degraded gracefully): {e}")
                
                return fallback_value
        
        return cast(Callable[..., T], wrapper)
    
    return decorator
