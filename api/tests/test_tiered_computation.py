"""
Tests for tiered computation.

This module contains tests for the tiered computation functionality.
"""
import pytest
import time
from unittest.mock import AsyncMock, patch

from api.core.tiered_computation import (
    tiered_computation,
    with_tiered_computation,
    cached_result,
    ComputationTier
)
from api.core.ai_config import ai_config


@pytest.mark.asyncio
async def test_should_use_complex():
    """Test the should_use_complex method."""
    # Reset the tiered computation state
    tiered_computation.last_complex_calculations = {}
    
    # Test with forced tier
    assert tiered_computation.should_use_complex("test_op", force_tier=ComputationTier.COMPLEX) is True
    assert tiered_computation.should_use_complex("test_op", force_tier=ComputationTier.SIMPLE) is False
    
    # Test with default tier set to simple
    original_default_tier = ai_config.computation.default_tier
    ai_config.computation.default_tier = ComputationTier.SIMPLE
    
    assert tiered_computation.should_use_complex("test_op") is False
    
    # Test with default tier set to complex
    ai_config.computation.default_tier = ComputationTier.COMPLEX
    
    # First call should use complex because we haven't done a complex calculation yet
    assert tiered_computation.should_use_complex("test_op") is True
    
    # Record a complex calculation
    tiered_computation.record_complex_calculation("test_op")
    
    # Subsequent call should not use complex until enough time has passed
    assert tiered_computation.should_use_complex("test_op") is False
    
    # Test after time has passed
    time_between = ai_config.computation.time_between_complex
    tiered_computation.last_complex_calculations["test_op"] = time.time() - time_between - 1
    
    assert tiered_computation.should_use_complex("test_op") is True
    
    # Restore original default tier
    ai_config.computation.default_tier = original_default_tier


@pytest.mark.asyncio
async def test_with_tiered_computation():
    """Test the with_tiered_computation decorator."""
    # Define simple and complex test functions
    async def simple_func(*args, **kwargs):
        return "simple"
    
    async def complex_func(*args, **kwargs):
        return "complex"
    
    # Create a decorated function
    @with_tiered_computation(simple_func, complex_func, "test_operation")
    async def decorated_func(*args, **kwargs):
        return "original"
    
    # Reset the tiered computation state
    tiered_computation.last_complex_calculations = {}
    
    # Test with forced tier
    assert await decorated_func(force_tier=ComputationTier.COMPLEX) == "complex"
    assert await decorated_func(force_tier=ComputationTier.SIMPLE) == "simple"
    
    # Test with complex tier configured
    original_default_tier = ai_config.computation.default_tier
    ai_config.computation.default_tier = ComputationTier.COMPLEX
    
    assert await decorated_func() == "complex"
    
    # Test exception handling - if complex fails, should fall back to simple
    failing_complex = AsyncMock(side_effect=Exception("Complex failed"))
    
    @with_tiered_computation(simple_func, failing_complex, "test_operation_fail")
    async def decorated_with_failing_complex(*args, **kwargs):
        return "original"
    
    # Should fall back to simple
    assert await decorated_with_failing_complex() == "simple"
    
    # Restore original default tier
    ai_config.computation.default_tier = original_default_tier


@pytest.mark.asyncio
async def test_cached_result():
    """Test the cached_result decorator."""
    # Create a mock expensive function that counts calls
    call_count = 0
    
    @cached_result(ttl_key="recommendations")
    async def expensive_function(param1, param2=None):
        nonlocal call_count
        call_count += 1
        return f"Result: {param1}-{param2}"
    
    # Test that caching works
    original_cache_enabled = ai_config.cache_enabled
    ai_config.cache_enabled = True
    
    # First call should execute the function
    result1 = await expensive_function("test", param2="value")
    assert result1 == "Result: test-value"
    assert call_count == 1
    
    # Second call with same parameters should use cache
    result2 = await expensive_function("test", param2="value")
    assert result2 == "Result: test-value"
    assert call_count == 1  # Call count should not increase
    
    # Call with different parameters should execute the function again
    result3 = await expensive_function("different")
    assert result3 == "Result: different-None"
    assert call_count == 2
    
    # Test with caching disabled
    ai_config.cache_enabled = False
    
    # Call should execute the function even with same parameters
    result4 = await expensive_function("test", param2="value")
    assert result4 == "Result: test-value"
    assert call_count == 3
    
    # Test cache clearing
    ai_config.cache_enabled = True
    
    # Call to verify caching is working
    await expensive_function("clear_test")
    assert call_count == 4
    
    await expensive_function("clear_test")  # Should use cache
    assert call_count == 4
    
    # Clear cache and verify it causes a new execution
    expensive_function.clear_cache()
    
    await expensive_function("clear_test")
    assert call_count == 5
    
    # Restore original cache setting
    ai_config.cache_enabled = original_cache_enabled
