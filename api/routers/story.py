"""
Story router.

This module defines the story endpoints.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status

from api.core.security import get_current_user
from api.models.user import User
from api.schemas.story import StoryCreate, StoryFeedResponse, StoryResponse
from api.services.story import StoryService
from api.services.user import UserService

router = APIRouter(tags=["stories"])


@router.post("/stories", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    story_create: StoryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    story_service: Annotated[StoryService, Depends()],
    user_service: Annotated[UserService, Depends()],
):
    """
    Create a new story.
    
    Args:
        story_create: Story creation data
        current_user: Current authenticated user
        story_service: Story service
        user_service: User service
        
    Returns:
        StoryResponse: Created story
    """
    # Create story
    story = await story_service.create_story(current_user.id, story_create)
    
    # Get current user for response
    author = await user_service.get_by_id(current_user.id)
    
    return StoryResponse(
        id=story.id,
        media_url=story.media_url,
        caption=story.caption,
        author={
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
        },
        created_at=story.created_at,
        expires_at=story.expires_at,
        views_count=story.views_count,
        likes_count=story.likes_count,
        is_viewed_by_user=False,
        is_liked_by_user=False,
    )


@router.get("/stories/feed", response_model=StoryFeedResponse)
async def get_stories_feed(
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    current_user: Annotated[User, Depends(get_current_user)],
    story_service: Annotated[StoryService, Depends()],
):
    """
    Get stories feed.
    
    Args:
        cursor: Pagination cursor
        limit: Maximum number of stories to return
        current_user: Current authenticated user
        story_service: Story service
        
    Returns:
        StoryFeedResponse: Stories feed response with stories
    """
    return await story_service.get_stories_feed(current_user.id, cursor, limit)


@router.get("/stories/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: str = Path(..., title="The ID of the story to get"),
    current_user: Annotated[User, Depends(get_current_user)],
    story_service: Annotated[StoryService, Depends()],
    user_service: Annotated[UserService, Depends()],
    background_tasks: BackgroundTasks = None,
):
    """
    Get a story.
    
    Args:
        story_id: Story ID
        current_user: Current authenticated user
        story_service: Story service
        user_service: User service
        background_tasks: Background tasks
        
    Returns:
        StoryResponse: The story
        
    Raises:
        HTTPException: If story not found or expired
    """
    # Get story
    story = await story_service.get_story(story_id)
    
    # Get author
    author = await user_service.get_by_id(story.author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story author not found",
        )
    
    # Check if viewed and liked
    view_id = f"{current_user.id}_{story_id}"
    view_doc = await story_service.db.collection("story_views").document(view_id).get()
    is_viewed_by_user = view_doc.exists
    
    like_id = f"{current_user.id}_{story_id}"
    like_doc = await story_service.db.collection("story_likes").document(like_id).get()
    is_liked_by_user = like_doc.exists
    
    # Track story view in background
    if background_tasks and not is_viewed_by_user:
        background_tasks.add_task(story_service.track_story_view, current_user.id, story_id)
        is_viewed_by_user = True  # Optimistically set to true
    
    return StoryResponse(
        id=story.id,
        media_url=story.media_url,
        caption=story.caption,
        author={
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
        },
        created_at=story.created_at,
        expires_at=story.expires_at,
        views_count=story.views_count,
        likes_count=story.likes_count,
        is_viewed_by_user=is_viewed_by_user,
        is_liked_by_user=is_liked_by_user,
    )


@router.post("/stories/{story_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_story(
    story_id: str = Path(..., title="The ID of the story to like"),
    current_user: Annotated[User, Depends(get_current_user)],
    story_service: Annotated[StoryService, Depends()],
):
    """
    Like a story.
    
    Args:
        story_id: Story ID
        current_user: Current authenticated user
        story_service: Story service
        
    Raises:
        HTTPException: If story not found or already liked
    """
    await story_service.like_story(current_user.id, story_id)


@router.delete("/stories/{story_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_story(
    story_id: str = Path(..., title="The ID of the story to unlike"),
    current_user: Annotated[User, Depends(get_current_user)],
    story_service: Annotated[StoryService, Depends()],
):
    """
    Unlike a story.
    
    Args:
        story_id: Story ID
        current_user: Current authenticated user
        story_service: Story service
        
    Raises:
        HTTPException: If story not found or not liked
    """
    await story_service.unlike_story(current_user.id, story_id)
