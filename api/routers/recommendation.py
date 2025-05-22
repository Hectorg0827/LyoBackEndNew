"""
Recommendation router.

This module defines the recommendation endpoints.
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from api.core.security import get_current_user
from api.models.user import User
from api.schemas.ai import CourseResponse
from api.schemas.user import UserProfile
from api.services.recommendation import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/users", response_model=List[UserProfile])
async def get_recommended_users(
    limit: int = Query(10, ge=1, le=50),
    exclude_following: bool = Query(True),
    current_user: Annotated[User, Depends(get_current_user)],
    recommendation_service: Annotated[RecommendationService, Depends()],
):
    """
    Get personalized user recommendations for discovery.
    
    Args:
        limit: Maximum number of users to recommend
        exclude_following: Whether to exclude users that the current user already follows
        current_user: Current authenticated user
        recommendation_service: Recommendation service
        
    Returns:
        List[UserProfile]: List of recommended users
    """
    return await recommendation_service.get_recommended_users(
        current_user.id, 
        limit=limit, 
        exclude_following=exclude_following
    )


@router.get("/courses", response_model=List[CourseResponse])
async def get_recommended_courses(
    limit: int = Query(5, ge=1, le=20),
    current_user: Annotated[User, Depends(get_current_user)],
    recommendation_service: Annotated[RecommendationService, Depends()],
):
    """
    Get personalized course recommendations with skill gap analysis.
    
    Args:
        limit: Maximum number of courses to recommend
        current_user: Current authenticated user
        recommendation_service: Recommendation service
        
    Returns:
        List[CourseResponse]: List of recommended courses
    """
    return await recommendation_service.get_recommended_courses(
        current_user.id, 
        limit=limit
    )
