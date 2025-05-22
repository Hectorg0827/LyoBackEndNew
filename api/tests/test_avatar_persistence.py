"""
Tests for Avatar persistence functionality.
"""
import pytest
import time
from api.core.avatar import AvatarService, AvatarContext, AvatarPersona
from api.db.avatar_cache import (
    get_cached_avatar_context,
    cache_avatar_context,
    invalidate_avatar_cache,
    cache_avatar_contexts_bulk,
    get_cached_avatar_contexts_bulk,
    invalidate_avatar_caches_bulk,
    get_cache_size,
    get_cache_stats,
    clear_expired_cache
)

@pytest.fixture
def avatar_service():
    """Create a test avatar service."""
    return AvatarService(
        max_conversation_history=10,
        model_timeout_seconds=1.0,
        session_timeout_seconds=300
    )

@pytest.mark.asyncio
async def test_context_persistence(avatar_service):
    """Test that context is correctly persisted and loaded."""
    user_id = "test_user_1"
    
    # Create and save context
    context = AvatarContext(
        user_id=user_id,
        topics_discussed=["python", "testing"],
        learning_goals=["master testing"],
        persona=AvatarPersona.TUTOR
    )
    avatar_service.contexts[user_id] = context
    
    # Save context
    saved_data = await avatar_service.save_context(user_id)
    assert saved_data["context"]["user_id"] == user_id
    assert saved_data["context"]["topics_discussed"] == ["python", "testing"]
    
    # Clear in-memory context
    del avatar_service.contexts[user_id]
    
    # Load context
    context_data = await avatar_service._get_context(user_id)
    assert context_data.user_id == user_id
    assert context_data.topics_discussed == ["python", "testing"]
    assert context_data.learning_goals == ["master testing"]
    assert context_data.persona == AvatarPersona.TUTOR

@pytest.mark.asyncio
async def test_conversation_persistence(avatar_service):
    """Test that conversation history is correctly persisted and loaded."""
    user_id = "test_user_2"
    
    # Add some messages
    await avatar_service.handle_message(
        user_id=user_id,
        message_text="Hello, I want to learn about testing"
    )
    
    # Get conversation before save
    conv_before = avatar_service.conversation_history[user_id]
    assert len(conv_before) > 0
    
    # Save context and conversation
    saved_data = await avatar_service.save_context(user_id)
    assert "conversation" in saved_data
    assert len(saved_data["conversation"]) > 0
    
    # Clear in-memory data
    del avatar_service.contexts[user_id]
    del avatar_service.conversation_history[user_id]
    
    # Load context and verify conversation
    await avatar_service._get_context(user_id)
    conv_after = avatar_service.conversation_history[user_id]
    assert len(conv_after) == len(conv_before)
    assert conv_after[0].content == conv_before[0].content

@pytest.mark.asyncio
async def test_redis_caching(avatar_service):
    """Test that Redis caching works correctly."""
    user_id = "test_user_3"
    
    # Create initial context
    context = AvatarContext(
        user_id=user_id,
        topics_discussed=["redis", "caching"],
    )
    avatar_service.contexts[user_id] = context
    
    # Save context (should update both Firestore and Redis)
    await avatar_service.save_context(user_id)
    
    # Clear in-memory context
    del avatar_service.contexts[user_id]
    
    # First load should come from Redis
    start_time = time.time()
    context_data = await avatar_service._get_context(user_id)
    redis_load_time = time.time() - start_time
    
    assert context_data.topics_discussed == ["redis", "caching"]
    
    # Clear everything
    del avatar_service.contexts[user_id]
    await avatar_service._redis.delete(f"avatar:{user_id}")
    
    # Second load should come from Firestore (slower)
    start_time = time.time()
    context_data = await avatar_service._get_context(user_id)
    firestore_load_time = time.time() - start_time
    
    assert context_data.topics_discussed == ["redis", "caching"]
    assert firestore_load_time > redis_load_time  # Redis should be faster

@pytest.mark.asyncio
async def test_cache_invalidation(avatar_service):
    """Test that cache invalidation works correctly."""
    user_id = "test_user_4"
    
    # Create and save context
    context = AvatarContext(
        user_id=user_id,
        topics_discussed=["cache", "invalidation"],
    )
    avatar_service.contexts[user_id] = context
    
    # Save context
    await avatar_service.save_context(user_id)
    
    # Verify it's in cache
    cached_data = await get_cached_avatar_context(user_id)
    assert cached_data is not None
    
    # Invalidate cache
    success = await invalidate_avatar_cache(user_id)
    assert success
    
    # Verify it's no longer in cache
    cached_data = await get_cached_avatar_context(user_id)
    assert cached_data is None

@pytest.mark.asyncio
async def test_bulk_cache_operations(avatar_service):
    """Test bulk cache operations."""
    # Create test contexts
    contexts = {
        "user1": AvatarContext(user_id="user1", topics_discussed=["topic1"]),
        "user2": AvatarContext(user_id="user2", topics_discussed=["topic2"]),
        "user3": AvatarContext(user_id="user3", topics_discussed=["topic3"]),
    }
    
    # Test bulk caching
    bulk_contexts = {
        user_id: context.to_dict() 
        for user_id, context in contexts.items()
    }
    results = await cache_avatar_contexts_bulk(bulk_contexts)
    assert all(results.values())
    
    # Test bulk retrieval
    cached = await get_cached_avatar_contexts_bulk(list(contexts.keys()))
    assert len(cached) == 3
    assert all(data is not None for data in cached.values())
    
    # Test bulk invalidation
    invalidation_results = await invalidate_avatar_caches_bulk(list(contexts.keys()))
    assert all(invalidation_results.values())
    
    # Verify all are invalidated
    cached = await get_cached_avatar_contexts_bulk(list(contexts.keys()))
    assert all(data is None for data in cached.values())

@pytest.mark.asyncio
async def test_cache_maintenance(avatar_service):
    """Test cache maintenance functions."""
    # Add some test data
    for i in range(3):
        user_id = f"test_user_{i}"
        context = AvatarContext(user_id=user_id)
        await cache_avatar_context(user_id, context.to_dict())
    
    # Test cache size
    size = await get_cache_size()
    assert size >= 3
    
    # Test cache stats
    stats = await get_cache_stats()
    assert stats["total_entries"] >= 3
    assert "memory_used" in stats
    assert "hit_rate" in stats
    
    # Test clearing expired entries
    cleared = await clear_expired_cache()
    assert cleared >= 0  # May be 0 if nothing is expired
