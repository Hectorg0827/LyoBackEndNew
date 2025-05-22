"""
Ads schemas for Lyo API.

This module defines schemas for ad operations.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field, HttpUrl

from api.schemas.base import BaseSchema


class AdPosition(str, Enum):
    """Ad position enumeration."""
    
    FEED = "feed"
    PROFILE = "profile"
    COURSE = "course"
    SEARCH = "search"


class AdFormat(str, Enum):
    """Ad format enumeration."""
    
    BANNER = "banner"
    NATIVE = "native"
    VIDEO = "video"


class Ad(BaseSchema):
    """Ad schema."""
    
    id: str
    campaign_id: str
    title: str
    description: Optional[str] = None
    image_url: HttpUrl
    destination_url: HttpUrl
    format: AdFormat
    position: AdPosition
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    bid: float  # Cost per impression in USD


class AdRequest(BaseSchema):
    """Ad request schema."""
    
    user_id: Optional[str] = None
    position: AdPosition
    limit: int = Field(1, ge=1, le=5)
    context_tags: Optional[List[str]] = None


class AdImpressionEvent(BaseSchema):
    """Ad impression event schema."""
    
    ad_id: str
    user_id: Optional[str] = None
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    position: AdPosition
    device_info: Optional[Dict[str, str]] = None


class AdClickEvent(BaseSchema):
    """Ad click event schema."""
    
    ad_id: str
    user_id: Optional[str] = None
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    position: AdPosition
    device_info: Optional[Dict[str, str]] = None
