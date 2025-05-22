"""
AI schemas for Lyo API.

This module defines schemas for AI operations.
"""
from enum import Enum
from typing import List, Optional, Union

from pydantic import Field, HttpUrl

from api.schemas.base import BaseSchema


class ChatMessage(BaseSchema):
    """Chat message schema."""
    
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseSchema):
    """Chat request schema."""
    
    prompt: str = Field(..., max_length=2000)
    lang: Optional[str] = None
    conversation_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = None


class ChatStreamResponse(BaseSchema):
    """Chat stream response schema."""
    
    text: str
    done: bool = False


class ResourceType(str, Enum):
    """Resource type enumeration."""
    
    BOOK = "book"
    VIDEO = "video"
    PODCAST = "podcast"
    ARTICLE = "article"
    COURSE = "course"
    CUSTOM = "custom"


class CourseResource(BaseSchema):
    """Course resource schema."""
    
    type: ResourceType
    title: str
    url: HttpUrl
    description: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[HttpUrl] = None
    duration: Optional[int] = None  # Duration in minutes


class CourseModule(BaseSchema):
    """Course module schema."""
    
    title: str
    description: str
    resources: List[CourseResource]
    order: int


class CourseRequest(BaseSchema):
    """Course request schema."""
    
    topic: str
    depth: int = Field(1, ge=1, le=5)  # From 1 (basic) to 5 (advanced)
    formats: List[ResourceType] = []
    lang: Optional[str] = None


class CourseResponse(BaseSchema):
    """Course response schema."""
    
    id: str
    title: str
    description: str
    modules: List[CourseModule]
    created_at: str
    updated_at: str
    creator_id: str
    lang: str
