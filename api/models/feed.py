"""
Feed models.

This module defines models for feed operations.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import HttpUrl

from api.db.firestore import FirestoreModel
from api.schemas.feed import PostType


class Post(FirestoreModel):
    """Post model."""
    
    collection_name = "posts"
    
    id: str
    author_id: str
    text: str
    media_url: Optional[HttpUrl] = None
    type: PostType = PostType.TEXT
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    comments_count: int = 0
    views_count: int = 0
    tags: List[str] = []
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: str) -> "Post":
        """
        Create a Post instance from a dictionary.
        
        Args:
            data: Dictionary containing post data
            doc_id: Document ID
            
        Returns:
            Post: Post instance
        """
        # Convert Firestore timestamps to datetime
        created_at = data.get("created_at")
        if isinstance(created_at, dict):
            created_at = datetime.fromtimestamp(created_at["seconds"])
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, dict):
            updated_at = datetime.fromtimestamp(updated_at["seconds"])
        
        return cls(
            id=doc_id,
            author_id=data.get("author_id"),
            text=data.get("text"),
            media_url=data.get("media_url"),
            type=data.get("type", PostType.TEXT),
            created_at=created_at or datetime.utcnow(),
            updated_at=updated_at or datetime.utcnow(),
            likes_count=data.get("likes_count", 0),
            comments_count=data.get("comments_count", 0),
            views_count=data.get("views_count", 0),
            tags=data.get("tags", []),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Post instance to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the Post
        """
        return {
            "author_id": self.author_id,
            "text": self.text,
            "media_url": str(self.media_url) if self.media_url else None,
            "type": self.type,
            "created_at": self.created_at,
            "updated_at": datetime.utcnow(),
            "likes_count": self.likes_count,
            "comments_count": self.comments_count,
            "views_count": self.views_count,
            "tags": self.tags,
        }


class Like(FirestoreModel):
    """Like model."""
    
    collection_name = "likes"
    
    id: str
    user_id: str
    post_id: str
    created_at: datetime
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: str) -> "Like":
        """
        Create a Like instance from a dictionary.
        
        Args:
            data: Dictionary containing like data
            doc_id: Document ID
            
        Returns:
            Like: Like instance
        """
        # Convert Firestore timestamp to datetime
        created_at = data.get("created_at")
        if isinstance(created_at, dict):
            created_at = datetime.fromtimestamp(created_at["seconds"])
        
        return cls(
            id=doc_id,
            user_id=data.get("user_id"),
            post_id=data.get("post_id"),
            created_at=created_at or datetime.utcnow(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Like instance to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the Like
        """
        return {
            "user_id": self.user_id,
            "post_id": self.post_id,
            "created_at": self.created_at,
        }


class Comment(FirestoreModel):
    """Comment model."""
    
    collection_name = "comments"
    
    id: str
    author_id: str
    post_id: str
    text: str
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: str) -> "Comment":
        """
        Create a Comment instance from a dictionary.
        
        Args:
            data: Dictionary containing comment data
            doc_id: Document ID
            
        Returns:
            Comment: Comment instance
        """
        # Convert Firestore timestamps to datetime
        created_at = data.get("created_at")
        if isinstance(created_at, dict):
            created_at = datetime.fromtimestamp(created_at["seconds"])
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, dict):
            updated_at = datetime.fromtimestamp(updated_at["seconds"])
        
        return cls(
            id=doc_id,
            author_id=data.get("author_id"),
            post_id=data.get("post_id"),
            text=data.get("text"),
            created_at=created_at or datetime.utcnow(),
            updated_at=updated_at or datetime.utcnow(),
            likes_count=data.get("likes_count", 0),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Comment instance to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the Comment
        """
        return {
            "author_id": self.author_id,
            "post_id": self.post_id,
            "text": self.text,
            "created_at": self.created_at,
            "updated_at": datetime.utcnow(),
            "likes_count": self.likes_count,
        }
