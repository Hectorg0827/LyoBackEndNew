"""
Content router.

This module defines the content endpoints.
"""
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from api.core.security import get_current_user
from api.models.user import User
from api.schemas.content import (
    ExternalBook,
    ExternalContentResponse,
    ExternalCourse,
    ExternalPodcast,
    ExternalVideo,
    UploadCompleteRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from api.services.content import ContentService

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/upload/sign-url", response_model=UploadUrlResponse)
async def get_upload_url(
    request: UploadUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    content_service: Annotated[ContentService, Depends()],
):
    """
    Get signed URL for upload.
    
    Args:
        request: Upload URL request
        current_user: Current authenticated user
        content_service: Content service
        
    Returns:
        UploadUrlResponse: Upload URL response
    """
    return await content_service.generate_upload_url(current_user.id, request)


@router.post("/upload/complete", response_model=Dict[str, str])
async def complete_upload(
    request: UploadCompleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    content_service: Annotated[ContentService, Depends()],
):
    """
    Complete upload process.
    
    Args:
        request: Upload complete request
        current_user: Current authenticated user
        content_service: Content service
        
    Returns:
        Dict[str, str]: Success response
    """
    return await content_service.complete_upload(current_user.id, request)


@router.get("/external/books", response_model=List[ExternalBook])
async def get_books(
    query: str = Query(..., min_length=2),
    current_user: Annotated[User, Depends(get_current_user)],
    content_service: Annotated[ContentService, Depends()],
):
    """
    Search for books.
    
    Args:
        query: Search query
        current_user: Current authenticated user
        content_service: Content service
        
    Returns:
        List[ExternalBook]: List of books
    """
    return await content_service.search_books(query)


@router.get("/external/videos", response_model=List[ExternalVideo])
async def get_videos(
    query: str = Query(..., min_length=2),
    current_user: Annotated[User, Depends(get_current_user)],
    content_service: Annotated[ContentService, Depends()],
):
    """
    Search for educational videos.
    
    Args:
        query: Search query
        current_user: Current authenticated user
        content_service: Content service
        
    Returns:
        List[ExternalVideo]: List of videos
    """
    return await content_service.search_videos(query)


@router.get("/external/podcasts", response_model=List[ExternalPodcast])
async def get_podcasts(
    query: str = Query(..., min_length=2),
    current_user: Annotated[User, Depends(get_current_user)],
    content_service: Annotated[ContentService, Depends()],
):
    """
    Search for educational podcasts.
    
    Args:
        query: Search query
        current_user: Current authenticated user
        content_service: Content service
        
    Returns:
        List[ExternalPodcast]: List of podcasts
    """
    return await content_service.search_podcasts(query)


@router.get("/external/courses", response_model=List[ExternalCourse])
async def get_courses(
    query: str = Query(..., min_length=2),
    current_user: Annotated[User, Depends(get_current_user)],
    content_service: Annotated[ContentService, Depends()],
):
    """
    Search for online courses.
    
    Args:
        query: Search query
        current_user: Current authenticated user
        content_service: Content service
        
    Returns:
        List[ExternalCourse]: List of courses
    """
    return await content_service.search_courses(query)


@router.get("/external", response_model=ExternalContentResponse)
async def search_all_external_content(
    query: str = Query(..., min_length=2),
    current_user: Annotated[User, Depends(get_current_user)],
    content_service: Annotated[ContentService, Depends()],
):
    """
    Search all external content types.
    
    Args:
        query: Search query
        current_user: Current authenticated user
        content_service: Content service
        
    Returns:
        ExternalContentResponse: Combined search results
    """
    # Run all searches in parallel
    import asyncio
    
    books_task = content_service.search_books(query)
    videos_task = content_service.search_videos(query)
    podcasts_task = content_service.search_podcasts(query)
    courses_task = content_service.search_courses(query)
    
    books, videos, podcasts, courses = await asyncio.gather(
        books_task, videos_task, podcasts_task, courses_task
    )
    
    return ExternalContentResponse(
        books=books,
        videos=videos,
        podcasts=podcasts,
        courses=courses,
    )
