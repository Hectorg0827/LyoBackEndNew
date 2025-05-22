"""
Rate limiting middleware for the application.

This module implements a Redis-based rate limiting middleware to protect API endpoints
from abuse.
"""
from typing import Callable, Dict, Optional, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
import time

from api.core.config import settings


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Redis-based rate limiting middleware.
    
    Implements a sliding window rate limiter with Redis.
    """
    
    def __init__(
        self,
        app,
        redis_client: Redis,
        rate_limit_per_minute: int = 60,
        rate_limit_per_day: int = 10000,
        whitelist_paths: Optional[list] = None,
        admin_ips: Optional[list] = None,
    ):
        """
        Initialize the rate limiter.
        
        Args:
            app: The FastAPI application
            redis_client: Redis client instance
            rate_limit_per_minute: Maximum requests per minute per IP
            rate_limit_per_day: Maximum requests per day per IP
            whitelist_paths: List of paths exempt from rate limiting
            admin_ips: List of admin IPs exempt from rate limiting
        """
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_per_day = rate_limit_per_day
        self.whitelist_paths = whitelist_paths or ["/api/v1/health", "/api/v1/docs", "/api/v1/redoc"]
        self.admin_ips = admin_ips or []
        
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process the request.
        
        Args:
            request: The incoming request
            call_next: The next middleware in the chain
            
        Returns:
            Response: The response from the next middleware or a 429 if rate limited
        """
        # Skip rate limiting for whitelisted paths
        if request.url.path in self.whitelist_paths:
            return await call_next(request)
            
        # Get client IP (considering X-Forwarded-For for proxy setups)
        client_ip = self._get_client_ip(request)
        
        # Skip rate limiting for admin IPs
        if client_ip in self.admin_ips:
            return await call_next(request)
        
        # Check if rate limited
        is_limited, headers = await self._is_rate_limited(client_ip)
        
        if is_limited:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers=headers,
            )
            
        # Process the request
        return await call_next(request)
        
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.
        
        Args:
            request: The incoming request
            
        Returns:
            str: The client IP address
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0]
        return request.client.host
        
    async def _is_rate_limited(self, client_ip: str) -> Tuple[bool, Dict[str, str]]:
        """
        Check if a client IP is rate limited.
        
        Implements a sliding window rate limiter using Redis sorted sets.
        
        Args:
            client_ip: The client IP address
            
        Returns:
            Tuple[bool, Dict]: A tuple with whether the client is rate limited and any headers to set
        """
        current_time = int(time.time())
        minute_key = f"rate_limit:{client_ip}:minute"
        day_key = f"rate_limit:{client_ip}:day"
        
        # Remove expired timestamps (older than 1 minute)
        one_minute_ago = current_time - 60
        await self.redis_client.zremrangebyscore(minute_key, 0, one_minute_ago)
        
        # Remove expired timestamps (older than 1 day)
        one_day_ago = current_time - 86400
        await self.redis_client.zremrangebyscore(day_key, 0, one_day_ago)
        
        # Add current timestamp
        pipe = self.redis_client.pipeline()
        pipe.zadd(minute_key, {current_time: current_time})
        pipe.zadd(day_key, {current_time: current_time})
        pipe.expire(minute_key, 60)
        pipe.expire(day_key, 86400)
        pipe.zcard(minute_key)
        pipe.zcard(day_key)
        results = await pipe.execute()
        
        # Get current counts
        minute_count = results[4]
        day_count = results[5]
        
        # Prepare headers
        headers = {
            "X-RateLimit-Limit-Minute": str(self.rate_limit_per_minute),
            "X-RateLimit-Remaining-Minute": str(max(0, self.rate_limit_per_minute - minute_count)),
            "X-RateLimit-Limit-Day": str(self.rate_limit_per_day),
            "X-RateLimit-Remaining-Day": str(max(0, self.rate_limit_per_day - day_count)),
        }
        
        # Check if rate limited
        if minute_count > self.rate_limit_per_minute or day_count > self.rate_limit_per_day:
            headers["Retry-After"] = "60" if minute_count > self.rate_limit_per_minute else "3600"
            return True, headers
            
        return False, headers


async def setup_rate_limiting(app, redis_client):
    """
    Set up rate limiting middleware.
    
    Args:
        app: The FastAPI application
        redis_client: Redis client instance
    """
    app.add_middleware(
        RateLimitingMiddleware,
        redis_client=redis_client,
        rate_limit_per_minute=settings.RATE_LIMIT_PER_MINUTE 
            if hasattr(settings, "RATE_LIMIT_PER_MINUTE") else 60,
        rate_limit_per_day=settings.RATE_LIMIT_PER_DAY
            if hasattr(settings, "RATE_LIMIT_PER_DAY") else 10000,
        whitelist_paths=settings.RATE_LIMIT_WHITELIST
            if hasattr(settings, "RATE_LIMIT_WHITELIST") else None,
        admin_ips=settings.ADMIN_IPS
            if hasattr(settings, "ADMIN_IPS") else None,
    )
