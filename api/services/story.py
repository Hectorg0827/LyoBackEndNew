"""
Story service.

This module provides services for story operations.
"""
import base64
import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from fastapi import Depends, HTTPException, status, Request

from api.db.firestore import db
from api.models.story import Story, StoryView
from api.schemas.story import StoryCreate, StoryFeedResponse, StoryResponse
from api.services.user import UserService
from api.core.error_utils_ai import handle_ai_errors, graceful_ai_degradation
from api.core.errors_ai import FeedProcessingError

logger = logging.getLogger(__name__)


class StoryService:
    """Story service."""
    
    def __init__(self, user_service: UserService = Depends()):
        """
        Initialize story service.
        
        Args:
            user_service: User service
        """
        self.user_service = user_service
        self.db = db

    async def create_story(
        self, author_id: str, story_create: StoryCreate
    ) -> Story:
        """
        Create a story.
        
        Args:
            author_id: Author ID
            story_create: Story creation data
            
        Returns:
            Story: Created story
            
        Raises:
            HTTPException: On error
        """
        # Check if user exists
        author = await self.user_service.get_by_id(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author not found",
            )
        
        # Create story with 24-hour expiration
        now = datetime.utcnow()
        story = Story(
            id="",  # Will be set after saving
            author_id=author_id,
            media_url=story_create.media_url,
            caption=story_create.caption,
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        
        try:
            story_id = await story.save()
            story.id = story_id
            return story
        except Exception as e:
            logger.error(f"Error creating story: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create story",
            )

    async def get_story(self, story_id: str) -> Story:
        """
        Get a story by ID.
        
        Args:
            story_id: Story ID
            
        Returns:
            Story: The story
            
        Raises:
            HTTPException: If story not found or expired
        """
        story = await Story.get_by_id(story_id)
        if not story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Story not found",
            )
        
        # Check if expired
        now = datetime.utcnow()
        if story.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Story has expired",
            )
            
        return story

    @graceful_ai_degradation(fallback_value=StoryFeedResponse(stories=[], next_cursor=None))
    async def get_stories_feed(
        self, user_id: str, cursor: Optional[str] = None, limit: int = 20
    ) -> StoryFeedResponse:
        """
        Get stories feed for a user.
        
        Stories are ordered by urgency (closest to expiration) and from users the user follows.
        
        Args:
            user_id: User ID
            cursor: Pagination cursor
            limit: Maximum number of stories to return
            
        Returns:
            StoryFeedResponse: Stories feed response
            
        Raises:
            FeedProcessingError: If story processing fails
        """
        try:
            # Get users the current user follows
            follows_ref = db.collection("follows").where("follower_id", "==", user_id)
            follows_docs = await follows_ref.get()
            
            followed_user_ids = [doc.get("following_id") for doc in follows_docs]
            # Always include the user's own stories
            if user_id not in followed_user_ids:
                followed_user_ids.append(user_id)
                
            # If user doesn't follow anyone, get some popular users
            if not followed_user_ids:
                # In a real app, this would fetch popular users
                # For simplicity, we'll just get some recent stories
                pass
            
            # Get non-expired stories from followed users
            now = datetime.utcnow()
            
            # Query stories
            query = db.collection("stories").where(
                "expires_at", ">", now
            ).where(
                "author_id", "in", followed_user_ids
            ).order_by(
                "expires_at", direction="ASCENDING"  # Urgency-based ordering
            ).limit(limit)
            
            # Apply cursor if provided
            if cursor:
                try:
                    cursor_bytes = base64.b64decode(cursor)
                    timestamp = datetime.fromtimestamp(int(cursor_bytes) / 1000)
                    query = query.start_after({
                        "expires_at": timestamp,
                    })
                except Exception as e:
                    logger.warning(f"Invalid cursor: {e}")
            
            # Execute query
            story_docs = await query.get()
            
            # Create stories
            stories = []
            for doc in story_docs:
                story = Story.from_dict(doc.to_dict(), doc.id)
                stories.append(story)
            
            # Get authors
            author_ids = [story.author_id for story in stories]
            authors = {}
            for author_id in author_ids:
                author = await self.user_service.get_by_id(author_id)
                if author:
                    authors[author_id] = author
            
            # Get viewed stories
            story_ids = [story.id for story in stories]
            viewed_stories = set()
            liked_stories = set()
            
            if story_ids:
                # Check viewed stories
                for story_id in story_ids:
                    view_id = f"{user_id}_{story_id}"
                    view_doc = await db.collection("story_views").document(view_id).get()
                    if view_doc.exists:
                        viewed_stories.add(story_id)
                
                # Check liked stories
                for story_id in story_ids:
                    like_id = f"{user_id}_{story_id}"
                    like_doc = await db.collection("story_likes").document(like_id).get()
                    if like_doc.exists:
                        liked_stories.add(story_id)
            
            # Build response items
            items = []
            for story in stories:
                author = authors.get(story.author_id)
                if not author:
                    continue  # Skip stories with missing author
                
                author_profile = {
                    "id": author.id,
                    "email": author.email,
                    "display_name": author.display_name,
                    "avatar_url": author.avatar_url,
                    "bio": author.bio,
                    "lang": author.lang,
                    "followers_count": getattr(author, "followers_count", 0),
                    "following_count": getattr(author, "following_count", 0),
                    "created_at": author.created_at,
                    "updated_at": author.updated_at,
                    "is_active": author.is_active,
                    "is_verified": author.is_verified,
                }
                
                items.append(
                    StoryResponse(
                        id=story.id,
                        media_url=story.media_url,
                        caption=story.caption,
                        author=author_profile,
                        created_at=story.created_at,
                        expires_at=story.expires_at,
                        views_count=story.views_count,
                        likes_count=story.likes_count,
                        is_viewed_by_user=story.id in viewed_stories,
                        is_liked_by_user=story.id in liked_stories,
                    )
                )
            
            # Create next cursor
            next_cursor = None
            if len(items) == limit and stories:
                last_story = stories[-1]
                expiry_timestamp = int(last_story.expires_at.timestamp() * 1000)
                next_cursor = base64.b64encode(str(expiry_timestamp).encode()).decode()
            
            return StoryFeedResponse(
                items=items,
                next_cursor=next_cursor,
            )
        except Exception as e:
            logger.error(f"Error getting stories feed: {e}")
            raise FeedProcessingError(
                detail=f"Failed to process stories feed: {str(e)}",
                feed_type="stories",
                algorithm_name="urgency_based_story_algorithm"
            )
            
    @handle_ai_errors
    async def track_story_view(self, user_id: str, story_id: str) -> None:
        """
        Track story view.
        
        Args:
            user_id: User ID
            story_id: Story ID
            
        Raises:
            FeedProcessingError: If tracking fails
        """
        try:
            # Check if story exists
            story = await self.get_story(story_id)
            
            # Check if already viewed
            view_id = f"{user_id}_{story_id}"
            view_ref = db.collection("story_views").document(view_id)
            view_doc = await view_ref.get()
            
            if view_doc.exists:
                return  # Already viewed
            
            # Create view
            now = datetime.utcnow()
            view = StoryView(
                id=view_id,
                user_id=user_id,
                story_id=story_id,
                created_at=now,
            )
            
            await view.save()
            
            # Update story views count
            story_ref = db.collection("stories").document(story_id)
            await story_ref.update({
                "views_count": story.views_count + 1,
            })
            
        except Exception as e:
            logger.error(f"Error tracking story view: {e}")
            raise FeedProcessingError(
                detail=f"Failed to track story view: {str(e)}",
                feed_type="stories",
                algorithm_name="engagement_tracking"
            )
            
    async def like_story(self, user_id: str, story_id: str) -> None:
        """
        Like a story.
        
        Args:
            user_id: User ID
            story_id: Story ID
            
        Raises:
            HTTPException: If story not found or already liked
        """
        # Check if story exists
        story = await self.get_story(story_id)
        
        try:
            # Check if already liked
            like_id = f"{user_id}_{story_id}"
            like_ref = db.collection("story_likes").document(like_id)
            like_doc = await like_ref.get()
            
            if like_doc.exists:
                return  # Already liked
            
            # Create like
            now = datetime.utcnow()
            await like_ref.set({
                "user_id": user_id,
                "story_id": story_id,
                "created_at": now,
            })
            
            # Update story likes count
            story_ref = db.collection("stories").document(story_id)
            await story_ref.update({
                "likes_count": story.likes_count + 1,
            })
            
        except Exception as e:
            logger.error(f"Error liking story: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to like story",
            )
            
    async def unlike_story(self, user_id: str, story_id: str) -> None:
        """
        Unlike a story.
        
        Args:
            user_id: User ID
            story_id: Story ID
            
        Raises:
            HTTPException: If story not found or not liked
        """
        # Check if story exists
        story = await self.get_story(story_id)
        
        try:
            # Check if liked
            like_id = f"{user_id}_{story_id}"
            like_ref = db.collection("story_likes").document(like_id)
            like_doc = await like_ref.get()
            
            if not like_doc.exists:
                return  # Not liked
            
            # Delete like
            await like_ref.delete()
            
            # Update story likes count
            story_ref = db.collection("stories").document(story_id)
            await story_ref.update({
                "likes_count": max(0, story.likes_count - 1),
            })
            
        except Exception as e:
            logger.error(f"Error unliking story: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unlike story",
            )
