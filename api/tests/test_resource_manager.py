"""
Tests for AI resource manager.

This module contains tests for the AI resource manager functionality.
"""
import pytest
import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch


from api.core.resource_manager import AIResourceManager, ai_resource_manager


class MockResource:
    """Mock resource for testing."""
    
    def __init__(self, resource_id: str):
        self.resource_id = resource_id
        self.is_closed = False
    
    async def close(self):
        self.is_closed = True


@pytest.mark.asyncio
@patch('api.core.resource_manager.get_embedding_model', new_callable=AsyncMock)
async def test_managed_embedding_resource(mock_get_embedding):
    """Test the managed_resource context manager with embedding resources."""
    # Set up the mock
    mock_embedding = MockResource("test_embedding")
    mock_get_embedding.return_value = mock_embedding
    
    # Create a new manager for testing
    manager = AIResourceManager()
    
    # Use the context manager
    async with manager.managed_resource("embedding", "test_model", dimension=512) as resource:
        # Verify the resource was initialized correctly
        assert resource is mock_embedding
        assert "embedding:test_model" in manager.active_resources
        assert manager.active_resources["embedding:test_model"]["resource"] is mock_embedding
    
    # Verify resource was cleaned up
    assert mock_embedding.is_closed is True
    assert "embedding:test_model" not in manager.active_resources
    
    # Verify the mock was called with the right parameters
    mock_get_embedding.assert_called_once_with(dimension=512)


@pytest.mark.asyncio
@patch('api.core.resource_manager.get_inference_model', new_callable=AsyncMock)
async def test_managed_model_resource(mock_get_model):
    """Test the managed_resource context manager with model resources."""
    # Set up the mock
    mock_model = MockResource("test_model")
    mock_get_model.return_value = mock_model
    
    # Use the context manager
    async with ai_resource_manager.managed_resource(
        "model", "recommendation_model", version="v2", batch_size=32
    ) as resource:
        # Verify the resource was initialized correctly
        assert resource is mock_model
        assert "model:recommendation_model" in ai_resource_manager.active_resources
    
    # Verify resource was cleaned up
    assert mock_model.is_closed is True
    assert "model:recommendation_model" not in ai_resource_manager.active_resources
    
    # Verify the mock was called with the right parameters
    mock_get_model.assert_called_once_with("recommendation_model", version="v2", batch_size=32)


@pytest.mark.asyncio
@patch('api.services.ai.get_embedding_model', new_callable=AsyncMock)
async def test_resource_cleanup_on_error(mock_get_embedding):
    """Test that resources are properly cleaned up when errors occur."""
    # Set up the mock
    mock_embedding = MockResource("test_embedding")
    mock_get_embedding.return_value = mock_embedding
    
    # Create a new manager for testing
    manager = AIResourceManager()
    
    # Use the context manager with an error inside
    try:
        async with manager.managed_resource("embedding", "test_model") as resource:
            # Verify the resource was initialized correctly
            assert resource is mock_embedding
            assert "embedding:test_model" in manager.active_resources
            
            # Raise an exception
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Verify resource was cleaned up despite the error
    assert mock_embedding.is_closed is True
    assert "embedding:test_model" not in manager.active_resources


@pytest.mark.asyncio
async def test_cleanup_resource_special_cases():
    """Test the _cleanup_resource method with different types of resources."""
    # Create resources with different cleanup methods
    class ResourceWithMethodClose:
        def __init__(self):
            self.is_closed = False
        
        def close(self):
            self.is_closed = True
    
    class ResourceWithAsyncClose:
        def __init__(self):
            self.is_closed = False
        
        async def close(self):
            self.is_closed = True
    
    class ResourceWithCleanup:
        def __init__(self):
            self.is_cleaned = False
        
        def cleanup(self):
            self.is_cleaned = True
    
    class ResourceWithDel:
        def __init__(self):
            self.is_deleted = False
        
        def __del__(self):
            self.is_deleted = True
    
    # Create a manager for testing
    manager = AIResourceManager()
    
    # Test with synchronous close method
    resource1 = ResourceWithMethodClose()
    manager.active_resources["test1"] = {"resource": resource1, "start_time": 0, "type": "test"}
    await manager._cleanup_resource("test1")
    assert resource1.is_closed is True
    assert "test1" not in manager.active_resources
    
    # Test with async close method
    resource2 = ResourceWithAsyncClose()
    manager.active_resources["test2"] = {"resource": resource2, "start_time": 0, "type": "test"}
    await manager._cleanup_resource("test2")
    assert resource2.is_closed is True
    assert "test2" not in manager.active_resources
    
    # Test with cleanup method
    resource3 = ResourceWithCleanup()
    manager.active_resources["test3"] = {"resource": resource3, "start_time": 0, "type": "test"}
    await manager._cleanup_resource("test3")
    assert resource3.is_cleaned is True
    assert "test3" not in manager.active_resources
    
    # Test with __del__ method
    resource4 = ResourceWithDel()
    manager.active_resources["test4"] = {"resource": resource4, "start_time": 0, "type": "test"}
    await manager._cleanup_resource("test4")
    # We can't reliably test __del__ behavior, but we can verify the resource was removed from tracking
    assert "test4" not in manager.active_resources
