"""
Notification schemas for Lyo API.

This module defines schemas for notification operations.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, HttpUrl

from api.schemas.base import BaseSchema
from api.schemas.user import UserProfile


class NotificationType(str, Enum):
    """Notification type enumeration."""
    
    FOLLOW = "follow"
    LIKE = "like"
    COMMENT = "comment"
    MENTION = "mention"
    SYSTEM = "system"
    MESSAGE = "message"


class Notification(BaseSchema):
    """Notification schema."""
    
    id: str
    type: NotificationType
    actor: Optional[UserProfile] = None
    target_id: Optional[str] = None
    target_type: Optional[str] = None
    message: str
    created_at: datetime
    is_read: bool = False
    image_url: Optional[HttpUrl] = None


class NotificationResponse(BaseSchema):
    """Notification response schema."""
    
    items: list[Notification]
    unread_count: int
    next_cursor: Optional[str] = None


class WebSocketEvent(BaseSchema):
    """WebSocket event schema."""
    
    event_type: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
