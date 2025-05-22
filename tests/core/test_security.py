"""
Tests for the security module.
"""
import jwt
import pytest
from datetime import datetime, timedelta
from unittest import mock

from fastapi import HTTPException

from api.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    decode_token,
)
from api.schemas.auth import TokenPayload


def test_password_hashing():
    """Test password hashing and verification."""
    password = "secretpassword123"
    hashed_password = get_password_hash(password)
    
    # Hashed password should be different from original
    assert password != hashed_password
    
    # Verification should work
    assert verify_password(password, hashed_password) is True
    
    # Wrong password should fail verification
    assert verify_password("wrongpassword", hashed_password) is False


def test_create_access_token():
    """Test creating an access token."""
    user_id = "user123"
    
    # Create token with default expiry
    token = create_access_token(subject=user_id)
    
    # Token should be a string
    assert isinstance(token, str)
    
    # Decode and verify token
    payload = jwt.decode(
        token,
        "test-key",  # This will be mocked
        algorithms=["HS256"],
    )
    
    # Token should have user_id in the subject claim
    assert payload["sub"] == user_id
    
    # Token should have token_type claim
    assert payload["token_type"] == "access"
    
    # Token should have expiry time
    assert "exp" in payload


@mock.patch("api.core.security.settings.SECRET_KEY", "test-key")
@mock.patch("api.core.security.settings.REFRESH_TOKEN_EXPIRE_DAYS", 7)
def test_create_refresh_token():
    """Test creating a refresh token."""
    user_id = "user123"
    
    # Create token
    token = create_refresh_token(subject=user_id)
    
    # Decode and verify token
    payload = jwt.decode(
        token,
        "test-key",
        algorithms=["HS256"],
    )
    
    # Token should have user_id in the subject claim
    assert payload["sub"] == user_id
    
    # Token should have token_type claim
    assert payload["token_type"] == "refresh"
    
    # Expiry should be around 7 days from now
    exp_time = datetime.fromtimestamp(payload["exp"])
    now = datetime.utcnow()
    difference = exp_time - now
    
    # Allow for slight time differences in test execution
    assert timedelta(days=6, hours=23) < difference < timedelta(days=7, hours=1)


@mock.patch("api.core.security.settings.SECRET_KEY", "test-key")
def test_decode_token_valid():
    """Test decoding a valid token."""
    user_id = "user123"
    
    # Create payload
    payload = {
        "sub": user_id,
        "token_type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=15),
    }
    
    # Create token
    token = jwt.encode(payload, "test-key", algorithm="HS256")
    
    # Decode token
    token_payload = decode_token(token)
    
    # Token payload should be valid
    assert isinstance(token_payload, TokenPayload)
    assert token_payload.sub == user_id


@mock.patch("api.core.security.settings.SECRET_KEY", "test-key")
def test_decode_token_expired():
    """Test decoding an expired token."""
    user_id = "user123"
    
    # Create payload with expired token
    payload = {
        "sub": user_id,
        "token_type": "access",
        "exp": datetime.utcnow() - timedelta(minutes=15),
    }
    
    # Create token
    token = jwt.encode(payload, "test-key", algorithm="HS256")
    
    # Decoding should raise an exception
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    
    # Exception should be 401 Unauthorized
    assert exc_info.value.status_code == 401
    assert "Token has expired" in exc_info.value.detail


@mock.patch("api.core.security.settings.SECRET_KEY", "test-key")
def test_decode_token_invalid():
    """Test decoding an invalid token."""
    # Create an invalid token (random string)
    token = "invalid.token.format"
    
    # Decoding should raise an exception
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    
    # Exception should be 401 Unauthorized
    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail
