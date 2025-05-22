"""
Feed router.

This module defines the feed endpoints.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status

from api.core.security import get_current_user
from api.models.user import User
from api.schemas.feed import CommentCreate, CommentResponse, FeedResponse, PostCreate, PostResponse
from api.services.feed import FeedService
from api.services.user import UserService

router = APIRouter(tags=["feed"])


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_create: PostCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    feed_service: Annotated[FeedService, Depends()],
    user_service: Annotated[UserService, Depends()],
):
    """
    Create a new post.
    
    Args:
        post_create: Post creation data
        background_tasks: Background tasks
        current_user: Current authenticated user
        feed_service: Feed service
        user_service: User service
        
    Returns:
        PostResponse: Created post
    """
    # Create post
    post = await feed_service.create_post(current_user.id, post_create)
    
    # Get current user for response
    author = await user_service.get_by_id(current_user.id)
    
    # Add background task to publish post to feed service
    # This would normally publish to Pub/Sub for feed fanout
    # background_tasks.add_task(publish_post_created, post.id)
    
    return PostResponse(
        id=post.id,
        text=post.text,
        media_url=post.media_url,
        type=post.type,
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
        created_at=post.created_at,
        updated_at=post.updated_at,
        likes_count=post.likes_count,
        comments_count=post.comments_count,
        views_count=post.views_count,
        is_liked_by_user=False,
        tags=post.tags,
    )


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    current_user: Annotated[User, Depends(get_current_user)],
    feed_service: Annotated[FeedService, Depends()],
):
    """
    Get user feed.
    
    Args:
        cursor: Pagination cursor
        limit: Maximum number of posts to return
        current_user: Current authenticated user
        feed_service: Feed service
        
    Returns:
        FeedResponse: Feed response with posts
    """
    return await feed_service.get_feed(current_user.id, cursor, limit)


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: str = Path(..., title="The ID of the post to get"),
    current_user: Annotated[User, Depends(get_current_user)],
    feed_service: Annotated[FeedService, Depends()],
    user_service: Annotated[UserService, Depends()],
    background_tasks: BackgroundTasks = None,
):
    """
    Get a post by ID.
    
    Args:
        post_id: Post ID
        current_user: Current authenticated user
        feed_service: Feed service
        user_service: User service
        background_tasks: Background tasks
        
    Returns:
        PostResponse: Post response
        
    Raises:
        HTTPException: If post not found
    """
    # Get post
    post = await feed_service.get_post(post_id)
    
    # Get author
    author = await user_service.get_by_id(post.author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post author not found",
        )
    
    # Check if user has liked post
    like_id = f"{current_user.id}_{post_id}"
    like_doc = await feed_service.db.collection("likes").document(like_id).get()
    is_liked_by_user = like_doc.exists
    
    # Track post view in background
    if background_tasks:
        background_tasks.add_task(feed_service.track_post_view, post_id)
    
    return PostResponse(
        id=post.id,
        text=post.text,
        media_url=post.media_url,
        type=post.type,
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
        created_at=post.created_at,
        updated_at=post.updated_at,
        likes_count=post.likes_count,
        comments_count=post.comments_count,
        views_count=post.views_count,
        is_liked_by_user=is_liked_by_user,
        tags=post.tags,
    )


@router.post("/posts/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_post(
    post_id: str = Path(..., title="The ID of the post to like"),
    current_user: Annotated[User, Depends(get_current_user)],
    feed_service: Annotated[FeedService, Depends()],
):
    """
    Like a post.
    
    Args:
        post_id: Post ID
        current_user: Current authenticated user
        feed_service: Feed service
        
    Raises:
        HTTPException: If post not found or already liked
    """
    await feed_service.like_post(current_user.id, post_id)


@router.delete("/posts/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_post(
    post_id: str = Path(..., title="The ID of the post to unlike"),
    current_user: Annotated[User, Depends(get_current_user)],
    feed_service: Annotated[FeedService, Depends()],
):
    """
    Unlike a post.
    
    Args:
        post_id: Post ID
        current_user: Current authenticated user
        feed_service: Feed service
        
    Raises:
        HTTPException: If post not found or not liked
    """
    await feed_service.unlike_post(current_user.id, post_id)


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    comment_create: CommentCreate,
    post_id: str = Path(..., title="The ID of the post to comment on"),
    current_user: Annotated[User, Depends(get_current_user)],
    feed_service: Annotated[FeedService, Depends()],
    user_service: Annotated[UserService, Depends()],
):
    """
    Add a comment to a post.
    
    Args:
        comment_create: Comment creation data
        post_id: Post ID
        current_user: Current authenticated user
        feed_service: Feed service
        user_service: User service
        
    Returns:
        CommentResponse: Created comment
        
    Raises:
        HTTPException: If post not found or on error
    """
    # Ensure post ID matches path
    if comment_create.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post ID in path must match post ID in body",
        )
    
    # Create comment
    comment = await feed_service.add_comment(current_user.id, comment_create)
    
    # Get author
    author = await user_service.get_by_id(current_user.id)
    
    return CommentResponse(
        id=comment.id,
        text=comment.text,
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
        post_id=comment.post_id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        likes_count=comment.likes_count,
        is_liked_by_user=False,
    )


@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_post_comments(
    post_id: str = Path(..., title="The ID of the post to get comments for"),
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    current_user: Annotated[User, Depends(get_current_user)],
    feed_service: Annotated[FeedService, Depends()],
    user_service: Annotated[UserService, Depends()],
):
    """
    Get comments for a post.
    
    Args:
        post_id: Post ID
        cursor: Pagination cursor
        limit: Maximum number of comments to return
        current_user: Current authenticated user
        feed_service: Feed service
        user_service: User service
        
    Returns:
        List[CommentResponse]: List of comments
        
    Raises:
        HTTPException: If post not found
    """
    # Get comments
    comments = await feed_service.get_post_comments(post_id, cursor, limit)
    
    # Get authors
    author_ids = [comment.author_id for comment in comments]
    authors = {}
    for author_id in author_ids:
        author = await user_service.get_by_id(author_id)
        if author:
            authors[author_id] = author
    
    # Get liked comments
    comment_ids = [comment.id for comment in comments]
    liked_comments = set()
    if comment_ids:
        # This would be more efficient with a batch query
        for comment_id in comment_ids:
            like_id = f"{current_user.id}_{comment_id}"
            like_doc = await feed_service.db.collection("comment_likes").document(like_id).get()
            if like_doc.exists:
                liked_comments.add(comment_id)
    
    # Build response
    response = []
    for comment in comments:
        author = authors.get(comment.author_id)
        if not author:
            continue  # Skip comments with missing author
            
        response.append(CommentResponse(
            id=comment.id,
            text=comment.text,
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
            post_id=comment.post_id,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            likes_count=comment.likes_count,
            is_liked_by_user=comment.id in liked_comments,
        ))
    
    return response
