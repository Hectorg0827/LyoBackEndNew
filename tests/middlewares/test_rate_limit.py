"""
Tests for rate limiting middleware.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from redis.asyncio import Redis
import time
from unittest import mock

from api.middlewares.rate_limit import RateLimitingMiddleware


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock_redis_client = mock.AsyncMock(spec=Redis)
    
    # Mock a pipeline for Redis commands
    mock_pipeline = mock.AsyncMock()
    mock_redis_client.pipeline.return_value = mock_pipeline
    
    # Configure pipeline execution results
    mock_pipeline.execute.return_value = [1, 1, True, True, 1, 1]  # Default values
    
    return mock_redis_client


@pytest.fixture
def test_app_with_rate_limit(mock_redis):
    """Create a test app with rate limiting middleware."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
    
    # Add rate limiting middleware
    app.add_middleware(
        RateLimitingMiddleware,
        redis_client=mock_redis,
        rate_limit_per_minute=2,
        rate_limit_per_day=5,
        whitelist_paths=["/whitelist"],
        admin_ips=["192.168.1.100"],
    )
    
    return app


def test_rate_limit_headers(test_app_with_rate_limit, mock_redis):
    """Test that rate limit headers are set correctly."""
    # Configure mock to return low usage counts
    mock_pipeline = mock_redis.pipeline.return_value
    mock_pipeline.execute.return_value = [1, 1, True, True, 1, 1]  # Request count: 1
    
    client = TestClient(test_app_with_rate_limit)
    response = client.get("/test", headers={"X-Forwarded-For": "127.0.0.1"})
    
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit-Minute"] == "2"
    assert response.headers["X-RateLimit-Remaining-Minute"] == "1"
    assert response.headers["X-RateLimit-Limit-Day"] == "5"
    assert response.headers["X-RateLimit-Remaining-Day"] == "4"


def test_rate_limit_exceeded_minute(test_app_with_rate_limit, mock_redis):
    """Test rate limiting when minute limit is exceeded."""
    # Configure mock to return high minute usage count
    mock_pipeline = mock_redis.pipeline.return_value
    mock_pipeline.execute.return_value = [1, 1, True, True, 3, 1]  # Minute count: 3, exceeds limit of 2
    
    client = TestClient(test_app_with_rate_limit)
    response = client.get("/test", headers={"X-Forwarded-For": "127.0.0.1"})
    
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]
    assert response.headers["Retry-After"] == "60"  # Minute retry
    
    # Check headers still set correctly
    assert response.headers["X-RateLimit-Limit-Minute"] == "2"
    assert response.headers["X-RateLimit-Remaining-Minute"] == "0"


def test_rate_limit_exceeded_day(test_app_with_rate_limit, mock_redis):
    """Test rate limiting when day limit is exceeded."""
    # Configure mock to return high day usage count
    mock_pipeline = mock_redis.pipeline.return_value
    mock_pipeline.execute.return_value = [1, 1, True, True, 1, 6]  # Day count: 6, exceeds limit of 5
    
    client = TestClient(test_app_with_rate_limit)
    response = client.get("/test", headers={"X-Forwarded-For": "127.0.0.1"})
    
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]
    assert response.headers["Retry-After"] == "3600"  # Hour retry
    
    # Check headers still set correctly
    assert response.headers["X-RateLimit-Limit-Day"] == "5"
    assert response.headers["X-RateLimit-Remaining-Day"] == "0"


def test_whitelist_path_not_rate_limited(test_app_with_rate_limit, mock_redis):
    """Test that whitelisted paths are not rate limited."""
    test_app_with_rate_limit.get("/whitelist")(lambda: {"message": "whitelisted"})
    
    # This should skip rate limiting entirely
    client = TestClient(test_app_with_rate_limit)
    response = client.get("/whitelist", headers={"X-Forwarded-For": "127.0.0.1"})
    
    assert response.status_code == 200
    
    # Redis should not be called for whitelisted paths
    mock_redis.pipeline.assert_not_called()


def test_admin_ip_not_rate_limited(test_app_with_rate_limit, mock_redis):
    """Test that admin IPs are not rate limited."""
    client = TestClient(test_app_with_rate_limit)
    response = client.get("/test", headers={"X-Forwarded-For": "192.168.1.100"})
    
    assert response.status_code == 200
    
    # Redis should not be called for admin IPs
    mock_redis.pipeline.assert_not_called()


def test_forwarded_ip_handling(test_app_with_rate_limit, mock_redis):
    """Test that X-Forwarded-For header is handled correctly."""
    # Configure mock for success case
    mock_pipeline = mock_redis.pipeline.return_value
    mock_pipeline.execute.return_value = [1, 1, True, True, 1, 1]
    
    client = TestClient(test_app_with_rate_limit)
    
    # Single IP
    response = client.get("/test", headers={"X-Forwarded-For": "10.0.0.1"})
    assert response.status_code == 200
    
    # Multiple IPs - should use the first one
    response = client.get("/test", headers={"X-Forwarded-For": "10.0.0.2, 10.0.0.3"})
    assert response.status_code == 200
    
    # Check the keys used with Redis to ensure correct IP extraction
    mock_calls = mock_redis.pipeline.mock_calls
    assert "rate_limit:10.0.0.1:minute" in str(mock_calls[0])
    assert "rate_limit:10.0.0.2:minute" in str(mock_calls[2])
