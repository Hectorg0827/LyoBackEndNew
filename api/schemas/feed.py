"""
Feed schemas for Lyo API.

This module defines schemas for feed operations.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import Field, HttpUrl

from api.schemas.base import BaseSchema
from api.schemas.user import UserProfile


class PostType(str, Enum):
    """Post type enumeration."""
    
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"
    COURSE = "course"


class PostCreate(BaseSchema):
    """Post creation schema."""
    
    text: str = Field(..., max_length=2000)
    media_url: Optional[HttpUrl] = None
    type: PostType = PostType.TEXT
    tags: List[str] = []


class PostResponse(BaseSchema):
    """Post response schema."""
    
    id: str
    text: str
    media_url: Optional[HttpUrl] = None
    type: PostType
    author: UserProfile
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    comments_count: int = 0
    views_count: int = 0
    is_liked_by_user: bool = False
    tags: List[str] = []


class CommentCreate(BaseSchema):
    """Comment creation schema."""
    
    text: str = Field(..., max_length=500)
    post_id: str


class CommentResponse(BaseSchema):
    """Comment response schema."""
    
    id: str
    text: str
    author: UserProfile
    post_id: str
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    is_liked_by_user: bool = False


class FeedResponse(BaseSchema):
    """Feed response schema."""
    
    items: List[PostResponse]
    next_cursor: Optional[str] = None
