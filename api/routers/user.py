"""
User router.

This module defines the user endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.core.security import get_current_user
from api.models.user import User
from api.schemas.base import SuccessResponse
from api.schemas.user import UserFollow, UserProfile, UserProfileUpdate
from api.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{uid}", response_model=UserProfile)
async def get_user(
    uid: str = Path(..., title="The ID of the user to get"),
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends()],
):
    """
    Get a user profile.
    
    Args:
        uid: User ID
        current_user: Current authenticated user
        user_service: User service
        
    Returns:
        UserProfile: User profile
        
    Raises:
        HTTPException: If user not found
    """
    user = await user_service.get_by_id(uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check if the current user is following this user
    is_following = False
    if uid != current_user.id:
        is_following = await user_service.is_following(current_user.id, uid)
    
    return UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        lang=user.lang,
        followers_count=getattr(user, "followers_count", 0),
        following_count=getattr(user, "following_count", 0),
        created_at=user.created_at,
        updated_at=user.updated_at,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


@router.patch("/{uid}", response_model=UserProfile)
async def update_user(
    user_update: UserProfileUpdate,
    uid: str = Path(..., title="The ID of the user to update"),
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends()],
):
    """
    Update a user profile.
    
    Args:
        user_update: User profile update data
        uid: User ID
        current_user: Current authenticated user
        user_service: User service
        
    Returns:
        UserProfile: Updated user profile
        
    Raises:
        HTTPException: If user not found or not authorized
    """
    # Check if user is authorized to update profile
    if uid != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile",
        )
    
    # Update user
    updated_user = await user_service.update_user(uid, user_update)
    
    return UserProfile(
        id=updated_user.id,
        email=updated_user.email,
        display_name=updated_user.display_name,
        avatar_url=updated_user.avatar_url,
        bio=updated_user.bio,
        lang=updated_user.lang,
        followers_count=getattr(updated_user, "followers_count", 0),
        following_count=getattr(updated_user, "following_count", 0),
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at,
        is_active=updated_user.is_active,
        is_verified=updated_user.is_verified,
    )


@router.post("/{uid}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def follow_user(
    follow: UserFollow,
    uid: str = Path(..., title="The ID of the user who is following"),
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends()],
):
    """
    Follow a user.
    
    Args:
        follow: Follow request data
        uid: User ID
        current_user: Current authenticated user
        user_service: User service
        
    Raises:
        HTTPException: If user not found or not authorized
    """
    # Check if user is authorized
    if uid != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to follow on behalf of this user",
        )
    
    # Follow user
    await user_service.follow_user(uid, follow.target_uid)


@router.delete("/{uid}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    follow: UserFollow,
    uid: str = Path(..., title="The ID of the user who is unfollowing"),
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends()],
):
    """
    Unfollow a user.
    
    Args:
        follow: Follow request data
        uid: User ID
        current_user: Current authenticated user
        user_service: User service
        
    Raises:
        HTTPException: If user not found or not authorized
    """
    # Check if user is authorized
    if uid != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to unfollow on behalf of this user",
        )
    
    # Unfollow user
    await user_service.unfollow_user(uid, follow.target_uid)
