"""
User service.

This module provides services for user operations.
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from google.cloud.firestore_v1.base_query import FieldFilter

from api.core.security import get_password_hash
from api.db.firestore import db
from api.models.user import User
from api.schemas.user import UserProfileUpdate

logger = logging.getLogger(__name__)


class UserService:
    """User service."""
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[User]: The user or None if not found
        """
        try:
            return await User.get_by_id(user_id)
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email.
        
        Args:
            email: The user email
            
        Returns:
            Optional[User]: The user or None if not found
        """
        try:
            users = await User.get_by_field("email", email)
            return users[0] if users else None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    async def create_user(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        lang: str = "en-US",
    ) -> User:
        """
        Create a new user.
        
        Args:
            email: User email
            password: User password
            display_name: User display name
            lang: User preferred language
            
        Returns:
            User: The created user
            
        Raises:
            HTTPException: If user already exists
        """
        # Check if user exists
        existing_user = await self.get_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Create user
        now = datetime.utcnow()
        display_name = display_name or email.split("@")[0]
        
        user = User(
            id="",  # Will be set after saving
            email=email,
            hashed_password=get_password_hash(password),
            display_name=display_name,
            lang=lang,
            created_at=now,
            updated_at=now,
        )
        
        try:
            user_id = await user.save()
            user.id = user_id
            return user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )
    
    async def update_user(
        self, user_id: str, user_update: UserProfileUpdate
    ) -> User:
        """
        Update a user profile.
        
        Args:
            user_id: User ID
            user_update: User profile update data
            
        Returns:
            User: The updated user
            
        Raises:
            HTTPException: If user not found
        """
        # Get existing user
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        # Update fields
        if user_update.display_name is not None:
            user.display_name = user_update.display_name
            
        if user_update.avatar_url is not None:
            user.avatar_url = user_update.avatar_url
            
        if user_update.bio is not None:
            user.bio = user_update.bio
            
        if user_update.lang is not None:
            user.lang = user_update.lang
            
        user.updated_at = datetime.utcnow()
        
        try:
            await user.save()
            return user
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user",
            )
    
    async def follow_user(self, user_id: str, target_id: str) -> None:
        """
        Follow a user.
        
        Args:
            user_id: The user ID
            target_id: The target user ID to follow
            
        Raises:
            HTTPException: If user or target not found, or on error
        """
        # Check if users exist
        user = await self.get_by_id(user_id)
        target = await self.get_by_id(target_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
            
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found",
            )
            
        if user_id == target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot follow yourself",
            )
        
        try:
            # Check if already following
            follow_ref = db.collection("follows").document(f"{user_id}_{target_id}")
            follow_doc = await follow_ref.get()
            
            if follow_doc.exists:
                return  # Already following
                
            # Create follow relationship
            await follow_ref.set({
                "follower_id": user_id,
                "following_id": target_id,
                "created_at": datetime.utcnow(),
            })
            
            # Update follower/following counts (transaction would be better)
            user_ref = db.collection("users").document(user_id)
            await user_ref.update({
                "following_count": {"increment": 1},
            })
            
            target_ref = db.collection("users").document(target_id)
            await target_ref.update({
                "followers_count": {"increment": 1},
            })
            
        except Exception as e:
            logger.error(f"Error following user {target_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to follow user",
            )
    
    async def unfollow_user(self, user_id: str, target_id: str) -> None:
        """
        Unfollow a user.
        
        Args:
            user_id: The user ID
            target_id: The target user ID to unfollow
            
        Raises:
            HTTPException: If user or target not found, or on error
        """
        # Check if users exist
        user = await self.get_by_id(user_id)
        target = await self.get_by_id(target_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
            
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found",
            )
        
        try:
            # Check if following
            follow_ref = db.collection("follows").document(f"{user_id}_{target_id}")
            follow_doc = await follow_ref.get()
            
            if not follow_doc.exists:
                return  # Not following
                
            # Remove follow relationship
            await follow_ref.delete()
            
            # Update follower/following counts
            user_ref = db.collection("users").document(user_id)
            await user_ref.update({
                "following_count": {"increment": -1},
            })
            
            target_ref = db.collection("users").document(target_id)
            await target_ref.update({
                "followers_count": {"increment": -1},
            })
            
        except Exception as e:
            logger.error(f"Error unfollowing user {target_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unfollow user",
            )
    
    async def is_following(self, user_id: str, target_id: str) -> bool:
        """
        Check if a user is following another.
        
        Args:
            user_id: The user ID
            target_id: The target user ID
            
        Returns:
            bool: True if following, False otherwise
        """
        try:
            follow_ref = db.collection("follows").document(f"{user_id}_{target_id}")
            follow_doc = await follow_ref.get()
            return follow_doc.exists
        except Exception as e:
            logger.error(f"Error checking following status: {e}")
            return False
