"""
Request ID middleware.

This middleware adds a unique request ID to each incoming request, which is
then included in the response headers. This is useful for request tracing
and correlation.
"""
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request ID to each request.
    
    Adds a unique ID to each request and includes it in response headers.
    """
    
    def __init__(self, app):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
        """
        super().__init__(app)
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process the request.
        
        Args:
            request: The incoming request
            call_next: The next middleware in the chain
            
        Returns:
            Response: The response from the next middleware
        """
        # Check if request already has an ID (e.g., from load balancer)
        request_id = request.headers.get("X-Request-ID")
        
        # Generate a new ID if none exists
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Add ID to request scope for use in application
        request.state.request_id = request_id
        
        # Process the request
        response = await call_next(request)
        
        # Add ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


def get_request_id(request: Request) -> str:
    """
    Get request ID from request.
    
    Args:
        request: The request object
        
    Returns:
        str: The request ID
    """
    return getattr(request.state, "request_id", "unknown")
