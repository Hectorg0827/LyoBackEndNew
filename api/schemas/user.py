"""
User schemas for Lyo API.

This module defines schemas for user operations.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr, Field, HttpUrl

from api.schemas.base import BaseSchema


class UserProfile(BaseSchema):
    """User profile schema."""
    
    id: str
    email: EmailStr
    display_name: str
    avatar_url: Optional[HttpUrl] = None
    bio: Optional[str] = None
    lang: str = "en-US"
    followers_count: int = 0
    following_count: int = 0
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    is_verified: bool = False
    is_admin: bool = False


class UserProfileUpdate(BaseSchema):
    """User profile update schema."""
    
    display_name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    bio: Optional[str] = None
    lang: Optional[str] = None


class UserFollow(BaseSchema):
    """User follow schema."""
    
    target_uid: str


class UserFollowResponse(BaseSchema):
    """User follow response schema."""
    
    id: str
    display_name: str
    avatar_url: Optional[HttpUrl] = None
    bio: Optional[str] = None
    is_following: bool
