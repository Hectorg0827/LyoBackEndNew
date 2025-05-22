"""
Auth router.

This module defines the auth endpoints.
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from api.core.errors import UnauthorizedError, BadRequestError, NotFoundError
from api.core.i18n import normalize_language_code
from api.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from api.models.user import User
from api.schemas.auth import RefreshToken, Token, UserCreate, UserLogin
from api.schemas.user import UserProfile
from api.services.user import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", 
    response_model=Token, 
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user account with email, password, and display name.",
    responses={
        201: {"description": "User successfully created with access tokens"},
        400: {"description": "Bad request, validation error"},
        409: {"description": "Email already registered"},
    },
)
async def register(
    user_create: UserCreate,
    user_service: Annotated[UserService, Depends()],
):
    """
    Register a new user.
    
    Args:
        user_create: User registration data
        user_service: User service
        
    Returns:
        Token: Access and refresh tokens
        
    Raises:
        HTTPException: If email is already registered
    """
    try:
        # Normalize language code
        lang = normalize_language_code(user_create.lang) if user_create.lang else "en-US"
        
        # Create user
        user = await user_service.create_user(
            email=user_create.email,
            password=user_create.password,
            display_name=user_create.display_name,
            lang=lang,
        )
        
        # Create tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
        )
    except ValueError as e:
        # Email already exists or other validation error
        raise BadRequestError(str(e))


@router.post(
    "/login", 
    response_model=Token,
    summary="Login user",
    description="Authenticate a user with email and password to receive access tokens.",
    responses={
        200: {"description": "User successfully authenticated with access tokens"},
        401: {"description": "Invalid email or password"},
    },
)
async def login(
    user_login: UserLogin,
    user_service: Annotated[UserService, Depends()],
):
    """
    Login a user.
    
    Args:
        user_login: User login data
        user_service: User service
        
    Returns:
        Token: Access and refresh tokens
        
    Raises:
        UnauthorizedError: If invalid credentials
    """
    # Get user by email
    user = await user_service.get_by_email(user_login.email)
    if not user:
        raise UnauthorizedError("Invalid email or password")
    
    # Verify password
    if not verify_password(user_login.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    
    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/refresh", 
    response_model=Token,
    summary="Refresh tokens",
    description="Use a refresh token to obtain new access and refresh tokens.",
    responses={
        200: {"description": "New tokens successfully generated"},
        401: {"description": "Invalid refresh token"},
    },
)
async def refresh_token(
    refresh: RefreshToken,
    user_service: Annotated[UserService, Depends()],
):
    """
    Refresh access token.
    
    Args:
        refresh: Refresh token
        user_service: User service
        
    Returns:
        Token: New access and refresh tokens
        
    Raises:
        UnauthorizedError: If invalid refresh token
    """
    from jose import JWTError, jwt
    from pydantic import ValidationError

    from api.core.config import settings
    from api.schemas.auth import TokenPayload
    
    try:
        payload = jwt.decode(
            refresh.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
        
        if token_data.sub is None or payload.get("token_type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")
    except (JWTError, ValidationError):
        raise UnauthorizedError("Invalid refresh token")
    
    # Get user
    user = await user_service.get_by_id(token_data.sub)
    if user is None:
        raise UnauthorizedError("User not found")
    
    # Create new tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get(
    "/me", 
    response_model=UserProfile,
    summary="Get current user profile",
    description="Get the profile of the currently authenticated user.",
    responses={
        200: {"description": "User profile retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get current user profile.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserProfile: User profile
    """
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        avatar_url=current_user.avatar_url,
        bio=current_user.bio,
        lang=current_user.lang,
        followers_count=getattr(current_user, "followers_count", 0),
        following_count=getattr(current_user, "following_count", 0),
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        is_admin=getattr(current_user, "is_admin", False),
    )
