"""
Auth schemas for Lyo API.

This module defines schemas for authentication operations.
"""
from typing import Optional

from pydantic import EmailStr, Field

from api.schemas.base import BaseSchema


class UserCreate(BaseSchema):
    """User creation schema."""
    
    email: EmailStr
    password: str = Field(..., min_length=8)
    display_name: Optional[str] = None
    lang: Optional[str] = None


class UserLogin(BaseSchema):
    """User login schema."""
    
    email: EmailStr
    password: str


class TokenPayload(BaseSchema):
    """Token payload schema."""
    
    sub: Optional[str] = None
    exp: Optional[int] = None


class Token(BaseSchema):
    """Token schema."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshToken(BaseSchema):
    """Refresh token schema."""
    
    refresh_token: str
