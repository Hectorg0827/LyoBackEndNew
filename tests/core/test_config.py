"""
Tests for the configuration module.
"""
import os
from unittest import mock

import pytest
from pydantic import ValidationError

from api.core.config import Settings


def test_settings_defaults():
    """Test the default settings."""
    settings = Settings(SECRET_KEY="test-key")
    
    assert settings.APP_NAME == "lyo-backend"
    assert settings.DEBUG is False
    assert settings.ENVIRONMENT == "development"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.SECRET_KEY == "test-key"


def test_settings_from_env_vars():
    """Test loading settings from environment variables."""
    with mock.patch.dict(os.environ, {
        "APP_NAME": "test-app",
        "DEBUG": "true",
        "ENVIRONMENT": "test",
        "SECRET_KEY": "env-secret-key",
        "POSTGRES_USER": "test-user",
        "POSTGRES_PASSWORD": "test-password",
        "POSTGRES_SERVER": "test-server",
        "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "test-db",
        "RATE_LIMIT_PER_MINUTE": "120",
    }):
        settings = Settings()
        
        assert settings.APP_NAME == "test-app"
        assert settings.DEBUG is True
        assert settings.ENVIRONMENT == "test"
        assert settings.SECRET_KEY == "env-secret-key"
        assert settings.POSTGRES_USER == "test-user"
        assert settings.RATE_LIMIT_PER_MINUTE == 120
        
        # Test the database URL assembly
        assert settings.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://test-user:test-password@test-server:5433/test-db"


def test_settings_missing_required():
    """Test validation error when required field is missing."""
    with pytest.raises(ValidationError):
        Settings()  # SECRET_KEY is required
