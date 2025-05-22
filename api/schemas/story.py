"""
Story schemas for Lyo API.

This module defines schemas for story operations.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field, HttpUrl

from api.schemas.base import BaseSchema


class StoryCreate(BaseSchema):
    """Story creation schema."""
    
    media_url: HttpUrl
    caption: Optional[str] = None


class StoryResponse(BaseSchema):
    """Story response schema."""
    
    id: str
    media_url: HttpUrl
    caption: Optional[str] = None
    author: Dict
    created_at: datetime
    expires_at: datetime
    views_count: int
    likes_count: int
    is_viewed_by_user: bool = False
    is_liked_by_user: bool = False
    

class StoryFeedResponse(BaseSchema):
    """Story feed response schema."""
    
    items: List[StoryResponse]
    next_cursor: Optional[str] = None
