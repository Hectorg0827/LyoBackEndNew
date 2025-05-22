""" caching helpers for Avatar context and conversation.
"""
import logging
import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from api.db.redis import (
    redis_get_json, 
    redis_set_json, 
    redis_delete,
    get_redis
)
from api.core.telemetry import meter
from fastapi import Depends
from functools import wraps
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Configuration with defaults - can be overridden via environment variables
# Import this here to avoid circular imports
from api.core.config import get_settings

class CacheConfig(BaseModel):
    """Configuration model for avatar caching system"""
    ttl: int = 3600  # Default: 1 hour
    prefix: str = "avatar:"
    enabled: bool = True
    max_retries: int = 3
    retry_delay: float = 0.5  # seconds
    use_tags: bool = False  # Whether to use cache tags for invalidation
    tags_key_prefix: str = "tags:"  # Prefix for tag keys
    partitions: int = 1  # Number of cache partitions for distribution (sharding)

def get_cache_config() -> CacheConfig:
    """Get cache configuration with values from environment variables"""
    settings = get_settings()
    return CacheConfig(
        ttl=settings.AVATAR_CACHE_TTL if hasattr(settings, 'AVATAR_CACHE_TTL') else 3600,
        prefix=settings.AVATAR_CACHE_PREFIX if hasattr(settings, 'AVATAR_CACHE_PREFIX') else "avatar:",
        enabled=settings.AVATAR_CACHE_ENABLED if hasattr(settings, 'AVATAR_CACHE_ENABLED') else True,
        max_retries=settings.AVATAR_CACHE_MAX_RETRIES if hasattr(settings, 'AVATAR_CACHE_MAX_RETRIES') else 3,
        retry_delay=settings.AVATAR_CACHE_RETRY_DELAY if hasattr(settings, 'AVATAR_CACHE_RETRY_DELAY') else 0.5,
        use_tags=settings.AVATAR_CACHE_USE_TAGS if hasattr(settings, 'AVATAR_CACHE_USE_TAGS') else False,
        tags_key_prefix=settings.AVATAR_CACHE_TAGS_PREFIX if hasattr(settings, 'AVATAR_CACHE_TAGS_PREFIX') else "tags:",
        partitions=settings.AVATAR_CACHE_PARTITIONS if hasattr(settings, 'AVATAR_CACHE_PARTITIONS') else 1,
    )

# Add cache metrics with more granular details
cache_hits = meter.create_counter(
    name="avatar.cache.hits",
    description="Number of Redis cache hits",
)

cache_misses = meter.create_counter(
    name="avatar.cache.misses",
    description="Number of Redis cache misses",
)

cache_errors = meter.create_counter(
    name="avatar.cache.errors",
    description="Number of Redis cache operation errors",
)

# Add latency histogram metrics
cache_operation_latency = meter.create_histogram(
    name="avatar.cache.operation.latency",
    description="Latency of Redis cache operations",
    unit="ms",
)

# Add cache size metric
cache_size = meter.create_gauge(
    name="avatar.cache.size",
    description="Number of entries in the avatar cache",
)

def with_cache_metrics(func):
    """Decorator to measure and record cache operation latency"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            operation = func.__name__
            latency_ms = (time.time() - start_time) * 1000
            cache_operation_latency.record(latency_ms, {"operation": operation})
            return result
        except Exception as e:
            operation = func.__name__
            cache_errors.add(1, {"operation": operation, "error": str(type(e).__name__)})
            latency_ms = (time.time() - start_time) * 1000
            cache_operation_latency.record(latency_ms, {"operation": operation, "status": "error"})
            raise
    return wrapper

class CacheException(Exception):
    """Base exception for avatar cache operations"""
    pass

class CacheConnectionError(CacheException):
    """Exception raised when Redis connection fails"""
    pass

class CacheOperationError(CacheException):
    """Exception raised when a cache operation fails"""
    pass

@with_cache_metrics
async def cache_avatar_context(user_id: str, context_data: Dict[str, Any], config: CacheConfig = Depends(get_cache_config)) -> bool:
    """Cache avatar context and conversation in Redis."""
    if not config.enabled:
        logger.debug(f"Cache disabled, skipping cache_avatar_context for {user_id}")
        return True
        
    try:
        key = f"{config.prefix}{user_id}"
        result = await redis_set_json(key, context_data, expire=config.ttl)
        if not result:
            cache_errors.add(1, {"operation": "set"})
        return result
    except Exception as e:
        logger.error(f"Failed to cache avatar context for {user_id}: {e}")
        cache_errors.add(1, {"operation": "set", "error": str(type(e).__name__)})
        raise CacheOperationError(f"Failed to cache avatar context: {str(e)}") from e

@with_cache_metrics
async def get_cached_avatar_context(user_id: str, config: CacheConfig = Depends(get_cache_config)) -> Optional[Dict[str, Any]]:
    """Get cached avatar context and conversation from Redis."""
    if not config.enabled:
        logger.debug(f"Cache disabled, skipping get_cached_avatar_context for {user_id}")
        cache_misses.add(1)
        return None
        
    try:
        key = f"{config.prefix}{user_id}"
        result = await redis_get_json(key)
        if result is not None:
            cache_hits.add(1)
        else:
            cache_misses.add(1)
        return result
    except Exception as e:
        logger.error(f"Failed to get cached avatar context for {user_id}: {e}")
        cache_errors.add(1, {"operation": "get", "error": str(type(e).__name__)})
        cache_misses.add(1)
        raise CacheOperationError(f"Failed to get cached avatar context: {str(e)}") from e

@with_cache_metrics
async def invalidate_avatar_cache(user_id: str, config: CacheConfig = Depends(get_cache_config)) -> bool:
    """
    Invalidate cached avatar context for a user.
    
    Args:
        user_id: User identifier
        config: Cache configuration
        
    Returns:
        bool: True if invalidation was successful
    """
    if not config.enabled:
        logger.debug(f"Cache disabled, skipping invalidate_avatar_cache for {user_id}")
        return True
        
    try:
        key = f"{config.prefix}{user_id}"
        await redis_delete(key)
        return True
    except Exception as e:
        logger.error(f"Failed to invalidate avatar cache for {user_id}: {e}")
        cache_errors.add(1, {"operation": "invalidate", "error": str(type(e).__name__)})
        raise CacheOperationError(f"Failed to invalidate avatar cache: {str(e)}") from e

@with_cache_metrics
async def cache_avatar_contexts_bulk(contexts: Dict[str, Dict[str, Any]], config: CacheConfig = Depends(get_cache_config)) -> Dict[str, bool]:
    """
    Cache multiple avatar contexts in Redis using pipeline for better performance.
    
    Args:
        contexts: Dictionary mapping user_ids to their context data
        config: Cache configuration
        
    Returns:
        Dictionary mapping user_ids to success status
    """
    if not config.enabled or not contexts:
        return {user_id: True for user_id in contexts}
        
    results = {}
    try:
        # Use Redis pipeline for bulk operations
        redis = await get_redis()
        pipeline = redis.pipeline()
        
        # Add all set operations to the pipeline
        for user_id, context_data in contexts.items():
            key = f"{config.prefix}{user_id}"
            pipeline.set(key, redis_set_json.serialize_to_json(context_data), ex=config.ttl)
        
        # Execute all operations in one go
        responses = await pipeline.execute()
        
        # Map responses back to user_ids
        for i, (user_id, _) in enumerate(contexts.items()):
            results[user_id] = bool(responses[i])
            
        return results
    except Exception as e:
        logger.error(f"Failed to bulk cache avatar contexts: {e}")
        cache_errors.add(1, {"operation": "bulk_set", "error": str(type(e).__name__)})
        # Fall back to individual operations on pipeline failure
        return {user_id: await cache_avatar_context(user_id, data, config) 
                for user_id, data in contexts.items()}

@with_cache_metrics
async def get_cached_avatar_contexts_bulk(user_ids: List[str], config: CacheConfig = Depends(get_cache_config)) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Get cached avatar contexts for multiple users using pipeline for better performance.
    
    Args:
        user_ids: List of user identifiers
        config: Cache configuration
        
    Returns:
        Dictionary mapping user_ids to their context data (None if not found)
    """
    if not config.enabled or not user_ids:
        return {user_id: None for user_id in user_ids}
        
    try:
        # Use Redis pipeline for bulk operations
        redis = await get_redis()
        pipeline = redis.pipeline()
        
        # Create keys and add get operations to pipeline
        keys = [f"{config.prefix}{user_id}" for user_id in user_ids]
        for key in keys:
            pipeline.get(key)
            
        # Execute all operations in one go
        responses = await pipeline.execute()
        
        # Process responses
        results = {}
        for i, user_id in enumerate(user_ids):
            if raw_data := responses[i]: # Sourcery suggestion: Use named expression
                try:
                    results[user_id] = redis_get_json.deserialize_from_json(raw_data)
                    cache_hits.add(1)
                except Exception as e:
                    logger.warning(f"Failed to deserialize cached data for {user_id}: {e}")
                    results[user_id] = None
                    cache_misses.add(1)
            else:
                results[user_id] = None
                cache_misses.add(1)
                
        return results
    except Exception as e:
        logger.error(f"Failed to bulk get cached avatar contexts: {e}")
        cache_errors.add(1, {"operation": "bulk_get", "error": str(type(e).__name__)})
        # Fall back to individual operations on pipeline failure
        return {user_id: await get_cached_avatar_context(user_id, config) for user_id in user_ids}

@with_cache_metrics
async def invalidate_avatar_caches_bulk(user_ids: List[str], config: CacheConfig = Depends(get_cache_config)) -> Dict[str, bool]:
    """
    Invalidate cached avatar contexts for multiple users using pipeline for better performance.
    
    Args:
        user_ids: List of user identifiers
        config: Cache configuration
        
    Returns:
        Dictionary mapping user_ids to invalidation success status
    """
    if not config.enabled or not user_ids:
        return {user_id: True for user_id in user_ids}
        
    results = {}
    try:
        # Use Redis pipeline for bulk operations
        redis = await get_redis()
        pipeline = redis.pipeline()
        
        # Add all delete operations to pipeline
        key_map = {f"{config.prefix}{user_id}": user_id for user_id in user_ids}
        for key in key_map: # Sourcery suggestion: Remove unnecessary .keys()
            pipeline.delete(key)
            
        # Execute all operations in one go
        responses = await pipeline.execute()
        
        # Map responses back to user_ids
        for i, key in enumerate(key_map):
            user_id = key_map[key]
            results[user_id] = bool(responses[i])
            
        return results
    except Exception as e:
        logger.error(f"Failed to bulk invalidate avatar caches: {e}")
        cache_errors.add(1, {"operation": "bulk_invalidate", "error": str(type(e).__name__)})
        # Fall back to individual operations on pipeline failure
        return {user_id: await invalidate_avatar_cache(user_id, config) for user_id in user_ids}

async def get_cache_size(config: CacheConfig = Depends(get_cache_config)) -> int:
    """
    Get the number of cached avatar contexts.
    
    Args:
        config: Cache configuration
        
    Returns:
        int: Number of cached contexts or -1 if error
    """
    if not config.enabled:
        return 0
        
    try:
        redis = await get_redis()
        key_pattern = f"{config.prefix}*"
        keys = await redis.keys(key_pattern)
        size = len(keys)
        cache_size.set(size)  # Update metrics gauge
        return size
    except Exception as e:
        logger.error(f"Failed to get cache size: {e}")
        return -1

async def clear_expired_cache(config: CacheConfig = Depends(get_cache_config)) -> int:
    """
    Clear expired avatar contexts from cache.
    This is typically not needed as Redis handles expiration automatically,
    but can be useful for maintenance.
    
    Args:
        config: Cache configuration
    
    Returns:
        int: Number of cleared entries or -1 if error
    """
    if not config.enabled:
        return 0
        
    try:
        cleared = 0
        redis = await get_redis()
        key_pattern = f"{config.prefix}*"
        keys = await redis.keys(key_pattern)
        for key in keys:
            # Check if TTL is <= 0 (expired or no TTL set)
            ttl = await redis.ttl(key)
            if ttl <= 0:
                await redis.delete(key)
                cleared += 1
                
        # Update metrics gauge after clearing
        new_size = await get_cache_size(config)
        if new_size >= 0:  # Only update if get_cache_size succeeded
            cache_size.set(new_size)
            
        return cleared
    except Exception as e:
        logger.error(f"Failed to clear expired cache: {e}")
        return -1

@with_cache_metrics
async def get_cache_stats(config: CacheConfig = Depends(get_cache_config)) -> Dict[str, Any]:
    """
    Get comprehensive cache statistics.
    
    Args:
        config: Cache configuration
    
    Returns:
        Dict with cache statistics including:
        - total_entries: Total number of cached contexts
        - memory_used: Approximate memory used by cache
        - hit_rate: Cache hit rate
        - avg_latency: Average operation latency in ms
        - p95_latency: 95th percentile latency in ms
    """
    if not config.enabled:
        return {"enabled": False}
        
    try:
        redis = await get_redis()
        total_entries = await get_cache_size(config)
        info = await redis.info("memory")
        memory_used = info.get("used_memory_human", "unknown")
        
        total_requests = cache_hits.get_count() + cache_misses.get_count()
        hit_rate = cache_hits.get_count() / total_requests if total_requests > 0 else 0
        
        # Get key memory statistics  
        memory_stats = {}
        if total_entries > 0 and total_entries < 1000:  # Limit to avoid performance impact
            # Sample a subset of keys to estimate average size
            key_pattern = f"{config.prefix}*"
            keys = await redis.keys(key_pattern)
            if keys:
                sample_keys = keys[:min(100, len(keys))]  # Take up to 100 keys
                sizes = [await redis.memory_usage(key) for key in sample_keys]
                avg_key_size = sum(size for size in sizes if size) / len([s for s in sizes if s])
                memory_stats = {
                    "avg_key_size_bytes": avg_key_size,
                    "estimated_total_bytes": avg_key_size * total_entries
                }
        
        return {
            "enabled": True,
            "total_entries": total_entries,
            "memory_used": memory_used,
            "memory_stats": memory_stats,
            "hit_rate": hit_rate,
            "hit_count": cache_hits.get_count(),
            "miss_count": cache_misses.get_count(),
            "error_count": cache_errors.get_count(),
            # Advanced metrics could be added here when OpenTelemetry metrics API supports it
            # "avg_latency_ms": cache_operation_latency.get_mean(),
            # "p95_latency_ms": cache_operation_latency.get_percentile(95),
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {
            "error": str(e),
            "hit_count": cache_hits.get_count(),
            "miss_count": cache_misses.get_count(),
            "error_count": cache_errors.get_count()
        }

@with_cache_metrics
async def get_cache_stats_detailed(config: CacheConfig = Depends(get_cache_config)) -> Dict[str, Any]:
    """
    Get very detailed cache statistics including key distribution and memory usage patterns.
    This is a potentially expensive operation and should be rate-limited in production.
    
    Args:
        config: Cache configuration
    
    Returns:
        Dict with detailed cache statistics
    """
    if not config.enabled:
        return {"enabled": False}
        
    try:
        redis = await get_redis()
        basic_stats = await get_cache_stats(config)
        
        # Get detailed key information
        key_pattern = f"{config.prefix}*"
        keys = await redis.keys(key_pattern)
        
        # Sample keys for detailed analysis (limit to avoid performance impact)
        sample_size = min(100, len(keys))
        sample_keys = keys[:sample_size] if keys else []
        
        # Key statistics
        key_stats = []
        if sample_keys:
            pipeline = redis.pipeline()
            for key in sample_keys:
                pipeline.ttl(key)
                pipeline.memory_usage(key)
                
            responses = await pipeline.execute()
            
            for i, key in enumerate(sample_keys):
                ttl = responses[i*2]
                size = responses[i*2+1]
                key_stats.append({
                    "key": key,
                    "ttl": ttl,
                    "size_bytes": size
                })
        
        # Tag statistics if enabled
        tag_stats = {}
        if config.use_tags:
            tag_key_pattern = f"{config.tags_key_prefix}*"
            tag_keys = await redis.keys(tag_key_pattern)
            
            for tag_key in tag_keys:
                tag = tag_key[len(config.tags_key_prefix):]
                count = await redis.scard(tag_key)
                tag_stats[tag] = count
        
        # Add additional server-side metrics from Redis INFO
        redis_info = await redis.info()
        memory_info = {k: v for k, v in redis_info.items() if 'memory' in k}
        keyspace_info = redis_info.get('keyspace', {})
        
        return {
            **basic_stats,
            "sample_key_stats": key_stats,
            "tag_stats": tag_stats,
            "redis_memory_info": memory_info,
            "redis_keyspace_info": keyspace_info,
            "sample_size": sample_size,
            "total_keys_sampled": len(sample_keys)
        }
    except Exception as e:
        logger.error(f"Failed to get detailed cache stats: {e}")
        return {
            "error": str(e),
            "basic_stats": await get_cache_stats(config)
        }

async def with_retry(func, *args, max_retries=3, retry_delay=0.5, **kwargs):
    """
    Helper function to retry a Redis operation with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Arguments to pass to the function
        max_retries: Maximum number of retries
        retry_delay: Base delay between retries (will be exponentially increased)
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result from the function
        
    Raises:
        CacheOperationError: If all retries fail
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Retry {attempt+1}/{max_retries} for {func.__name__} after {wait_time:.2f}s: {str(last_exception)}") # Sourcery suggestion: Use previously assigned local variable
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} retries failed for {func.__name__}: {str(last_exception)}") # Sourcery suggestion: Use previously assigned local variable
                break
                
    raise CacheOperationError(f"Operation failed after {max_retries} retries") from last_exception


def get_partition_key(user_id: str, config: CacheConfig = Depends(get_cache_config)) -> str:
    """
    Calculate the partition key for a user ID to distribute cache entries.
    This improves cache distribution when dealing with large datasets.
    
    Args:
        user_id: User identifier
        config: Cache configuration
        
    Returns:
        str: Formatted key with partition
    """
    if config.partitions <= 1:
        return f"{config.prefix}{user_id}"
        
    # Simple hash function to distribute keys
    partition = hash(user_id) % config.partitions
    return f"{config.prefix}p{partition}:{user_id}"

@with_cache_metrics
async def cache_avatar_context_with_tags(
    user_id: str, 
    context_data: Dict[str, Any], 
    tags: List[str] = None
) -> bool:
    """
    Cache avatar context and conversation in Redis with optional tags for advanced invalidation.
    
    Args:
        user_id: User identifier
        context_data: Context data to cache
        tags: Optional list of tags to associate with this cache entry
        
    Returns:
        bool: True if caching was successful
    """
    config = get_cache_config()
    if not config.enabled:
        return True
    
    if not tags or not config.use_tags:
        # Fall back to regular caching if tags not provided or tag support disabled
        return await cache_avatar_context(user_id, context_data)
    
    try:
        redis = await get_redis()
        pipeline = redis.pipeline()
        
        # Use partitioning if configured
        key = get_partition_key(user_id, config)
        
        # Set the main cache entry
        pipeline.set(key, redis_set_json.serialize_to_json(context_data), ex=config.ttl)
        
        # Associate this key with each tag
        for tag in tags:
            tag_key = f"{config.tags_key_prefix}{tag}"
            pipeline.sadd(tag_key, key)
            pipeline.expire(tag_key, config.ttl * 2)  # Use longer TTL for tags
            
        # Execute all operations in one go
        results = await pipeline.execute()
        success = results[0] if results else False
        
        if not success:
            cache_errors.add(1, {"operation": "set_with_tags"})
            
        return success
    except Exception as e:
        logger.error(f"Failed to cache avatar context with tags for {user_id}: {e}")
        cache_errors.add(1, {"operation": "set_with_tags", "error": str(type(e).__name__)})
        # Fall back to regular caching
        return await cache_avatar_context(user_id, context_data)
        
@with_cache_metrics
async def invalidate_by_tag(tag: str) -> int:
    """
    Invalidate all cache entries associated with a specific tag.
    
    Args:
        tag: The tag to invalidate
        
    Returns:
        int: Number of invalidated entries
    """
    config = get_cache_config()
    if not config.enabled or not config.use_tags:
        return 0
        
    try:
        redis = await get_redis()
        tag_key = f"{config.tags_key_prefix}{tag}"
        
        # Get all keys associated with this tag
        keys = await redis.smembers(tag_key)
        
        if not keys:
            return 0
            
        # Delete all associated keys and the tag set itself
        pipeline = redis.pipeline()
        for key_bytes in keys: # redis.smembers returns bytes
            pipeline.delete(key_bytes) # pass bytes directly
        pipeline.delete(tag_key)
        
        results = await pipeline.execute()
        
        # Count successful deletions (excluding the tag key deletion itself)
        invalidated = sum(r for r in results[:-1] if r) # Simplified sum
        
        logger.info(f"Invalidated {invalidated} cache entries with tag '{tag}'")
        return invalidated
    except Exception as e:
        logger.error(f"Failed to invalidate cache by tag {tag}: {e}")
        cache_errors.add(1, {"operation": "invalidate_by_tag", "error": str(type(e).__name__)})
        return 0

@with_cache_metrics
async def perform_cache_maintenance() -> Dict[str, Any]:
    """
    Perform comprehensive cache maintenance operations:
    1. Clear expired entries
    2. Update cache size metrics
    3. Clean up orphaned tags
    4. Report cache health statistics
    
    This function is designed to be called periodically by a scheduler.
    
    Returns:
        Dict with maintenance statistics
    """
    config = get_cache_config()
    if not config.enabled:
        return {"enabled": False}
        
    start_time = time.time()
    stats = {
        "enabled": True,
        "timestamp": time.time(),
    }
    
    try:
        # Clear any expired entries
        cleared = await clear_expired_cache()
        stats["cleared_entries"] = cleared
        
        # Get current cache size and update gauge
        size = await get_cache_size()
        stats["current_size"] = size
        
        # Clean up orphaned tags (tags that don't point to any keys)
        if config.use_tags:
            orphaned_tags = 0
            redis = await get_redis()
            tag_pattern = f"{config.tags_key_prefix}*"
            tag_keys = await redis.keys(tag_pattern)
            
            for tag_key in tag_keys:
                # Check if this tag has any members
                count = await redis.scard(tag_key)
                if count == 0:
                    # This is an orphaned tag with no keys
                    await redis.delete(tag_key)
                    orphaned_tags += 1
                    
            stats["orphaned_tags_removed"] = orphaned_tags
            
        # Get basic cache stats
        cache_stats = await get_cache_stats()
        stats.update({
            "hit_rate": cache_stats.get("hit_rate", 0),
            "hit_count": cache_stats.get("hit_count", 0),
            "miss_count": cache_stats.get("miss_count", 0),
            "error_count": cache_stats.get("error_count", 0)
        })
        
    except Exception as e:
        logger.error(f"Cache maintenance failed: {e}")
        stats["error"] = str(e)
    
    # Calculate maintenance duration
    duration_ms = (time.time() - start_time) * 1000
    stats["maintenance_duration_ms"] = duration_ms
    
    return stats
