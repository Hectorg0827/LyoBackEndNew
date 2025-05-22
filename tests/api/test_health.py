"""
Tests for the health check endpoint.
"""
import pytest
from fastapi.testclient import TestClient

from api.core.config import settings


def test_health_check(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/api/v1/health")
    
    # Check status code
    assert response.status_code == 200
    
    # Check response data
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["environment"] == settings.ENVIRONMENT
