"""
Tests for content moderation.

This module contains tests for the content moderation functionality.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from api.core.content_moderation import content_moderator


@pytest.mark.asyncio
async def test_check_text_content_pattern_match():
    """Test that pattern matching detects prohibited content."""
    # Test with a pattern that should be caught
    result, reason, confidence = await content_moderator.check_text_content(
        "This text contains hate speech and should be flagged."
    )
    
    assert result is False
    assert reason is not None
    assert confidence > 0.5


@pytest.mark.asyncio
async def test_check_text_content_safe():
    """Test that safe content passes moderation."""
    # Test with harmless content
    result, reason, confidence = await content_moderator.check_text_content(
        "This is a perfectly fine message about learning and collaboration."
    )
    
    assert result is True
    assert reason is None
    assert confidence > 0.5


@pytest.mark.asyncio
@patch('api.core.resource_manager.ai_resource_manager.managed_resource')
async def test_check_image_content_unsafe(mock_resource_manager):
    """Test image moderation with mock model that detects unsafe content."""
    # Set up mock model
    mock_model = AsyncMock()
    mock_model.analyze.return_value = {
        "is_safe": False,
        "reason": "Detected prohibited content",
        "confidence": 0.95
    }
    
    # Set up context manager mock
    mock_context = MagicMock()
    mock_context.__aenter__.return_value = mock_model
    mock_resource_manager.return_value = mock_context
    
    # Test with an image URL
    result, reason, confidence = await content_moderator.check_image_content("https://example.com/image.jpg")
    
    # Verify results
    assert result is False
    assert reason == "Detected prohibited content"
    assert confidence == 0.95


@pytest.mark.asyncio
async def test_moderate_ai_response():
    """Test that AI response moderation works."""
    with patch.object(content_moderator, 'check_text_content') as mock_check:
        # Set up mock to return unsafe content
        mock_check.return_value = (False, "Prohibited content", 0.9)
        
        # Attempt to moderate an AI response
        response, was_moderated = await content_moderator.moderate_ai_response(
            "Let me tell you how to hack into a system...",
            {"intent": "educational"}
        )
        
        # Verify response was moderated
        assert was_moderated is True
        assert "I'm sorry" in response


@pytest.mark.asyncio
async def test_check_user_content_structured():
    """Test moderation of structured user content with both text and images."""
    # Create mock for the individual content checks
    with patch.object(content_moderator, 'check_text_content') as mock_text_check, \
         patch.object(content_moderator, 'check_image_content') as mock_image_check:
        
        # Set up mocks
        mock_text_check.return_value = (True, None, 0.9)
        mock_image_check.return_value = (True, None, 0.8)
        
        # Test with structured content
        content = {
            "title": "My post title",
            "text": "Post content here",
            "image_url": "https://example.com/image.jpg"
        }
        
        result, reason = await content_moderator.check_user_content("post", content, user_id="user123")
        
        # Verify results
        assert result is True
        assert reason is None
        
        # Verify that both text and image checks were called
        mock_text_check.assert_called_once()
        mock_image_check.assert_called_once_with("https://example.com/image.jpg", {"source": "user_generated", "content_type": "post", "user_id": "user123"})
