"""
AI router.

This module defines the AI endpoints.
"""
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse

from api.core.i18n import normalize_language_code
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.ai import ChatRequest, CourseRequest, CourseResponse
from api.services.ai import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    ai_service: Annotated[AIService, Depends()],
):
    """
    Chat with avatar using Gemma 3.
    
    Args:
        request: Chat request
        current_user: Current authenticated user
        ai_service: AI service
        
    Returns:
        StreamingResponse: Stream of chat responses
    """
    # Normalize language code
    if request.lang:
        request.lang = normalize_language_code(request.lang)
    else:
        request.lang = current_user.lang
        
    # Get chat response stream
    response_stream = ai_service.chat(current_user.id, request)
    
    async def stream_generator():
        """Generate SSE stream."""
        try:
            async for response in response_stream:
                if response.done:
                    yield f"data: [DONE]\n\n"
                    break
                yield f"data: {response.text}\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
            yield f"data: [DONE]\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
    )


@router.post("/course", response_model=CourseResponse)
async def generate_course(
    request: CourseRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    ai_service: Annotated[AIService, Depends()],
):
    """
    Generate course outline.
    
    Args:
        request: Course request
        current_user: Current authenticated user
        ai_service: AI service
        
    Returns:
        CourseResponse: Generated course
    """
    # Normalize language code
    if request.lang:
        request.lang = normalize_language_code(request.lang)
    else:
        request.lang = current_user.lang
        
    return await ai_service.generate_course(current_user.id, request)


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str = Path(..., title="The ID of the course to get"),
    current_user: Annotated[User, Depends(get_current_user)],
    ai_service: Annotated[AIService, Depends()],
):
    """
    Get course by ID.
    
    Args:
        course_id: Course ID
        current_user: Current authenticated user
        ai_service: AI service
        
    Returns:
        CourseResponse: Course
        
    Raises:
        HTTPException: If course not found
    """
    return await ai_service.get_course(course_id, current_user.id)


@router.patch("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    updates: Dict[str, Any] = Body(...),
    course_id: str = Path(..., title="The ID of the course to update"),
    current_user: Annotated[User, Depends(get_current_user)],
    ai_service: Annotated[AIService, Depends()],
):
    """
    Update course.
    
    Args:
        updates: Updates to apply
        course_id: Course ID
        current_user: Current authenticated user
        ai_service: AI service
        
    Returns:
        CourseResponse: Updated course
        
    Raises:
        HTTPException: If course not found or not authorized
    """
    return await ai_service.update_course(course_id, current_user.id, updates)
