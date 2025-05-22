"""
Tests for AI error handling.

This module contains tests for the AI error handling functionality.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from api.core.errors_ai import (
    RecommendationError,
    FeedProcessingError,
    AIQuotaExceededError,
    ModelExecutionError
)
from api.core.error_utils_ai import (
    handle_ai_errors,
    graceful_ai_degradation,
    handle_ai_error
)
from api.core.errors import setup_error_handlers

# Create test app
app = FastAPI()
setup_error_handlers(app)


# Test routes that raise different AI errors
@app.get("/test/recommendation-error")
@handle_ai_errors
async def test_recommendation_error():
    raise RecommendationError(
        detail="Test recommendation error",
        recommendation_type="user"
    )


@app.get("/test/feed-error")
@handle_ai_errors
async def test_feed_error():
    raise FeedProcessingError(
        detail="Test feed processing error",
        feed_type="main",
        algorithm_name="test_algorithm"
    )


@app.get("/test/quota-exceeded")
@handle_ai_errors
async def test_quota_exceeded():
    raise AIQuotaExceededError(
        detail="Test quota exceeded",
        quota_type="recommendations",
        reset_time=3600
    )


@app.get("/test/model-error")
@handle_ai_errors
async def test_model_error():
    raise ModelExecutionError(
        detail="Test model error",
        model_name="user_affinity",
        error_type="prediction_failure"
    )


@app.get("/test/graceful-degradation")
@graceful_ai_degradation(fallback_value={"status": "degraded", "value": []})
async def test_graceful_degradation():
    raise FeedProcessingError(
        detail="This error should be caught and degraded gracefully"
    )


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_recommendation_error_response(client):
    """Test that recommendation error returns the correct response."""
    response = client.get("/test/recommendation-error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "recommendation_error"
    assert "recommendation_type" in response.json()["error"]
    assert response.json()["error"]["recommendation_type"] == "user"


def test_feed_error_response(client):
    """Test that feed error returns the correct response."""
    response = client.get("/test/feed-error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "feed_processing_error"
    assert "feed_type" in response.json()["error"]
    assert "algorithm_name" in response.json()["error"]


def test_quota_exceeded_response(client):
    """Test that quota exceeded error returns the correct response with headers."""
    response = client.get("/test/quota-exceeded")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ai_quota_exceeded"
    assert "Retry-After" in response.headers
    assert response.headers["Retry-After"] == "3600"


def test_model_error_response(client):
    """Test that model error returns the correct response."""
    response = client.get("/test/model-error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "model_execution_error"
    assert "model_name" in response.json()["error"]
    assert "error_type" in response.json()["error"]


def test_graceful_degradation(client):
    """Test that graceful degradation returns the fallback value instead of an error."""
    response = client.get("/test/graceful-degradation")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "value" in response.json()


async def test_handle_ai_error():
    """Test the handle_ai_error utility function."""
    # Create mock request and response
    class MockRequest:
        url = type('obj', (object,), {'path': '/test'})
        method = "GET"
        headers = {"User-Agent": "test-agent"}
        cookies = {}
        state = type('obj', (object,), {'user_id': 123})
    
    class MockResponse:
        pass
    
    request = MockRequest()
    response = MockResponse()
    error = RecommendationError(detail="Test error")
    
    # Call the function
    error_context = await handle_ai_error(request, response, error)
    
    # Check the results
    assert error_context["user_id"] == 123
    assert error_context["path"] == "/test"
    assert error_context["error_type"] == "RecommendationError"
