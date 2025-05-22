"""
Content schemas for Lyo API.

This module defines schemas for content operations.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import Field, HttpUrl

from api.schemas.base import BaseSchema


class ContentType(str, Enum):
    """Content type enumeration."""
    
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class UploadUrlRequest(BaseSchema):
    """Upload URL request schema."""
    
    mime_type: str
    file_name: Optional[str] = None
    content_type: ContentType = ContentType.IMAGE


class UploadUrlResponse(BaseSchema):
    """Upload URL response schema."""
    
    signed_url: HttpUrl
    resource_id: str
    expires_at: datetime


class UploadCompleteRequest(BaseSchema):
    """Upload complete request schema."""
    
    resource_id: str


class ExternalBook(BaseSchema):
    """External book schema."""
    
    id: str
    title: str
    authors: List[str]
    publisher: Optional[str] = None
    published_date: Optional[str] = None
    description: Optional[str] = None
    page_count: Optional[int] = None
    categories: List[str] = []
    image_url: Optional[HttpUrl] = None
    info_link: HttpUrl
    preview_link: Optional[HttpUrl] = None
    language: str = "en"


class ExternalVideo(BaseSchema):
    """External video schema."""
    
    id: str
    title: str
    channel: str
    channel_id: str
    description: Optional[str] = None
    published_at: datetime
    duration: str  # ISO 8601 duration
    thumbnail_url: HttpUrl
    video_url: HttpUrl
    view_count: Optional[int] = None
    language: Optional[str] = None


class ExternalPodcast(BaseSchema):
    """External podcast schema."""
    
    id: str
    title: str
    author: str
    description: Optional[str] = None
    published_at: datetime
    duration: Optional[int] = None  # Duration in seconds
    image_url: Optional[HttpUrl] = None
    audio_url: HttpUrl
    rss_url: Optional[HttpUrl] = None
    language: Optional[str] = None


class ExternalCourse(BaseSchema):
    """External course schema."""
    
    id: str
    title: str
    provider: str
    instructor: Optional[str] = None
    description: Optional[str] = None
    url: HttpUrl
    image_url: Optional[HttpUrl] = None
    level: Optional[str] = None
    topics: List[str] = []
    duration: Optional[int] = None  # Duration in minutes
    language: str = "en"


class ExternalContentResponse(BaseSchema):
    """External content response schema."""
    
    books: Optional[List[ExternalBook]] = None
    videos: Optional[List[ExternalVideo]] = None
    podcasts: Optional[List[ExternalPodcast]] = None
    courses: Optional[List[ExternalCourse]] = None
