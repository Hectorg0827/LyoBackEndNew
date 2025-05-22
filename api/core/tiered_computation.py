"""
Tiered computation module for AI operations.

This module provides utilities for implementing tiered computation strategies.
"""
import asyncio
import functools
import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast

from fastapi import Request

from api.core.ai_config import ai_config
from api.core.resource_manager import ai_resource_manager
from api.core.telemetry import model_inference_time

logger = logging.getLogger(__name__)

# Type variable for function return type
T = TypeVar("T")
R = TypeVar("R")


class ComputationTier:
    """Computation tier enumeration."""
    
    SIMPLE = 1
    COMPLEX = 2


class TieredComputation:
    """Manager for tiered computation strategies."""
    
    def __init__(self):
        self.last_complex_calculations: Dict[str, float] = {}
    
    def should_use_complex(self, operation_id: str, force_tier: Optional[int] = None) -> bool:
        """
        Determine whether to use the complex computation tier.
        
        Args:
            operation_id: Identifier for the operation
            force_tier: Force a specific tier (for testing)
            
        Returns:
            bool: Whether to use complex computation
        """
        # If tiered computation is disabled, always use complex
        if not ai_config.computation.enabled:
            return True
            
        # If force_tier is specified, use that
        if force_tier is not None:
            return force_tier >= ComputationTier.COMPLEX
        
        # If default tier is complex, check time since last complex calculation
        current_time = time.time()
        last_calculation = self.last_complex_calculations.get(operation_id, 0)
        
        # Use complex tier if enough time has passed since the last complex calculation
        # or if the default tier is complex and we haven't done a complex calculation yet
        return (
            ai_config.computation.default_tier >= ComputationTier.COMPLEX and
            (current_time - last_calculation >= ai_config.computation.time_between_complex)
        )
    
    def record_complex_calculation(self, operation_id: str) -> None:
        """
        Record that a complex calculation was performed.
        
        Args:
            operation_id: Identifier for the operation
        """
        self.last_complex_calculations[operation_id] = time.time()


# Create a singleton instance
tiered_computation = TieredComputation()


def with_tiered_computation(
    simple_func: Callable[..., T],
    complex_func: Callable[..., T],
    operation_id: str
):
    """
    Decorator for implementing tiered computation.
    
    Args:
        simple_func: Function implementing the simple algorithm
        complex_func: Function implementing the complex algorithm
        operation_id: Identifier for the operation
        
    Returns:
        Decorated function that chooses between simple and complex implementations
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if force_tier is specified
            force_tier = kwargs.pop("force_tier", None)
            
            # Determine which tier to use
            use_complex = tiered_computation.should_use_complex(operation_id, force_tier)
            
            start_time = time.time()
            try:
                if use_complex:
                    logger.debug(f"Using complex algorithm for {operation_id}")
                    result = await complex_func(*args, **kwargs)
                    tiered_computation.record_complex_calculation(operation_id)
                else:
                    logger.debug(f"Using simple algorithm for {operation_id}")
                    result = await simple_func(*args, **kwargs)
                    
                # Record timing
                duration_ms = (time.time() - start_time) * 1000
                model_inference_time.record(
                    duration_ms,
                    {
                        "operation": operation_id,
                        "tier": "complex" if use_complex else "simple",
                    }
                )
                
                return result
            except Exception as e:
                # If complex calculation fails, try simple as fallback
                if use_complex:
                    logger.warning(
                        f"Complex algorithm failed for {operation_id}, falling back to simple: {str(e)}"
                    )
                    return await simple_func(*args, **kwargs)
                # Otherwise re-raise
                raise
                
        return cast(Callable[..., T], wrapper)
    return decorator


def cached_result(ttl_key: str):
    """
    Decorator for caching expensive computation results.
    
    Args:
        ttl_key: Key in AIConfig.computation.cache_ttl for TTL value
        
    Returns:
        Decorated function with caching
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        cache = {}
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip caching if disabled
            if not ai_config.cache_enabled:
                return await func(*args, **kwargs)
                
            # Generate a cache key from args and kwargs
            # This is a simple implementation - in production you might use more sophisticated key generation
            key_parts = [str(arg) for arg in args]
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key = f"{func.__name__}:{':'.join(key_parts)}"
            
            # Check if result is in cache and not expired
            current_time = time.time()
            if cache_key in cache:
                cached_time, cached_result = cache[cache_key]
                ttl = ai_config.computation.cache_ttl.get(ttl_key, 60)  # Default to 60 seconds
                
                if current_time - cached_time < ttl:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached_result
            
            # If not in cache or expired, call the function
            result = await func(*args, **kwargs)
            
            # Cache the result with current timestamp
            cache[cache_key] = (current_time, result)
            
            # Clean up old cache entries (optional)
            # This is a simple implementation - in production you might use a more sophisticated cache invalidation strategy
            if len(cache) > 1000:  # Limit cache size
                # Remove oldest entries
                oldest_keys = sorted(cache.items(), key=lambda x: x[1][0])[:100]
                for key, _ in oldest_keys:
                    del cache[key]
            
            return result
        
        # Add a method to clear the cache
        wrapper.clear_cache = lambda: cache.clear()
        
        return wrapper
    
    return decorator
