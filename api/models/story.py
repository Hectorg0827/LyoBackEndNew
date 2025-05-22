"""
Story models.

This module defines models for story operations.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import HttpUrl

from api.db.firestore import FirestoreModel


class Story(FirestoreModel):
    """Story model with auto-expiration (24 hours from creation)."""
    
    collection_name = "stories"
    
    id: str
    author_id: str
    media_url: HttpUrl  # Stories must have media
    caption: Optional[str] = None
    created_at: datetime
    expires_at: datetime  # Automatically set to 24h after creation
    views_count: int = 0
    likes_count: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: str) -> "Story":
        """
        Create a Story instance from a dictionary.
        
        Args:
            data: Dictionary containing story data
            doc_id: Document ID
            
        Returns:
            Story: Story instance
        """
        # Convert Firestore timestamps to datetime
        created_at = data.get("created_at")
        if isinstance(created_at, dict):
            created_at = datetime.fromtimestamp(created_at["seconds"])
        
        expires_at = data.get("expires_at")
        if isinstance(expires_at, dict):
            expires_at = datetime.fromtimestamp(expires_at["seconds"])
        
        return cls(
            id=doc_id,
            author_id=data.get("author_id"),
            media_url=data.get("media_url"),
            caption=data.get("caption"),
            created_at=created_at or datetime.utcnow(),
            expires_at=expires_at or (datetime.utcnow() + timedelta(hours=24)),
            views_count=data.get("views_count", 0),
            likes_count=data.get("likes_count", 0),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation
        """
        return {
            "author_id": self.author_id,
            "media_url": str(self.media_url),
            "caption": self.caption,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "views_count": self.views_count,
            "likes_count": self.likes_count,
        }


class StoryView(FirestoreModel):
    """Story view model for tracking user views of stories."""
    
    collection_name = "story_views"
    
    id: str  # user_id_story_id
    user_id: str
    story_id: str
    created_at: datetime
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: str) -> "StoryView":
        """
        Create a StoryView instance from a dictionary.
        
        Args:
            data: Dictionary containing story view data
            doc_id: Document ID
            
        Returns:
            StoryView: StoryView instance
        """
        # Convert Firestore timestamps to datetime
        created_at = data.get("created_at")
        if isinstance(created_at, dict):
            created_at = datetime.fromtimestamp(created_at["seconds"])
        
        return cls(
            id=doc_id,
            user_id=data.get("user_id"),
            story_id=data.get("story_id"),
            created_at=created_at or datetime.utcnow(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation
        """
        return {
            "user_id": self.user_id,
            "story_id": self.story_id,
            "created_at": self.created_at,
        }
