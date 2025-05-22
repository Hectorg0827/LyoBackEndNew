"""
API endpoints for AI Avatar and Classroom.

This module contains API endpoints for the AI Avatar and Classroom systems,
including user interactions and content generation.
"""
import logging
from typing import Dict, List, Optional, Union, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from api.core.avatar import AvatarPersona, avatar_service
from api.core.classroom import DifficultyLevel, lesson_service
from api.core.content_assembly import ContentSequenceType, LearningStyle, content_assembly_service
from api.core.content_retrieval import content_retrieval_service
from api.models.user import User
from api.core.security import get_current_user

logger = logging.getLogger(__name__)


# Request and response models
class AvatarMessageRequest(BaseModel):
    """Request for sending a message to the avatar."""
    
    message: str
    session_id: Optional[str] = None
    media_url: Optional[str] = None


class AvatarMessageResponse(BaseModel):
    """Response from the avatar."""
    
    text: str
    timestamp: float
    detected_topics: Optional[List[str]] = None
    moderated: Optional[bool] = None
    include_reaction_buttons: Optional[bool] = None
    suggest_advanced_content: Optional[bool] = None


class AvatarContextRequest(BaseModel):
    """Request to update avatar context."""
    
    topics: Optional[List[str]] = None
    learning_goals: Optional[List[str]] = None
    current_module: Optional[str] = None
    persona: Optional[str] = None
    learning_style: Optional[str] = None
    learning_pace: Optional[str] = None
    strengths: Optional[List[str]] = None
    areas_for_improvement: Optional[List[str]] = None
    preferred_resources: Optional[List[str]] = None


class AvatarContextResponse(BaseModel):
    """Response with avatar context data."""
    
    topics_covered: List[str]
    learning_goals: List[str]
    current_module: Optional[str] = None
    engagement_level: float
    last_interaction: float


class LessonRequest(BaseModel):
    """Request to generate a lesson."""
    
    subject: str
    topic: str
    difficulty: str = "beginner"
    duration: int = 30  # minutes


class QuizRequest(BaseModel):
    """Request to generate a quiz."""
    
    subject: str
    topic: str
    difficulty: str = "beginner"
    num_questions: int = 5


class CurriculumRequest(BaseModel):
    """Request to generate a curriculum."""
    
    subject: str
    topics: List[str]
    difficulty: str = "beginner"
    learning_style: Optional[str] = None
    sequence_type: str = "linear"


class LearningPathwayRequest(BaseModel):
    """Request to generate a learning pathway."""
    
    subject: str
    starting_level: str = "beginner"
    target_level: str = "intermediate"
    include_external_content: bool = True


class ContentSearchRequest(BaseModel):
    """Request to search for external content."""
    
    query: str
    content_types: List[str] = ["video", "book", "course", "podcast"]
    max_results_per_type: int = 5
    safe_search: bool = True


# Create router
router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/avatar/message", response_model=AvatarMessageResponse)
async def send_message_to_avatar(
    request: AvatarMessageRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the AI avatar and get a response.
    
    Args:
        request: Message request
        current_user: Authenticated user
        
    Returns:
        Avatar's response
    """
    try:
        response = await avatar_service.handle_message(
            user_id=current_user.id,
            message_text=request.message,
            session_id=request.session_id,
            media_url=request.media_url,
        )
        
        return AvatarMessageResponse(**response)
    except Exception as e:
        logger.error(f"Error handling avatar message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing message"
        )


@router.get("/avatar/context", response_model=AvatarContextResponse)
async def get_avatar_context(
    current_user: User = Depends(get_current_user),
):
    """
    Get the user's avatar context.
    
    Args:
        current_user: Authenticated user
        
    Returns:
        Avatar context data
    """
    try:
        # First ensure context is loaded from storage if needed
        await avatar_service._get_context(user_id=current_user.id)
        context = avatar_service.get_progress_summary(user_id=current_user.id)
        return AvatarContextResponse(**context)
    except Exception as e:
        logger.error(f"Error getting avatar context: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving avatar context"
        )


@router.post("/avatar/context", response_model=AvatarContextResponse)
async def update_avatar_context(
    request: AvatarContextRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Update the user's avatar context.
    
    Args:
        request: Context update request
        current_user: Authenticated user
        
    Returns:
        Updated avatar context
    """
    try:
        # Get the current context
        context = await avatar_service._get_context(user_id=current_user.id)
        
        # Update topics if provided
        if request.topics:
            for topic in request.topics:
                context.add_topic(topic)
        
        # Update learning goals if provided
        if request.learning_goals:
            for goal in request.learning_goals:
                context.set_learning_goal(goal)
        
        # Update current module if provided
        if request.current_module is not None:
            if request.current_module:
                context.set_current_module(request.current_module)
            else:
                context.clear_current_module()
        
        # Update persona if provided
        if request.persona:
            try:
                # Corrected: Call switch_persona on the context object
                context.switch_persona(AvatarPersona(request.persona))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid persona: {request.persona}"
                )
        
        # Update learning style if provided
        if request.learning_style:
            context.set_learning_style(request.learning_style)

        # Update learning pace if provided
        if request.learning_pace:
            context.set_learning_pace(request.learning_pace)

        # Update strengths if provided
        if request.strengths:
            for strength in request.strengths:
                context.add_strength(strength)
        
        # Update areas for improvement if provided
        if request.areas_for_improvement:
            for area in request.areas_for_improvement:
                context.add_area_for_improvement(area)

        # Update preferred resources if provided
        if request.preferred_resources:
            for resource in request.preferred_resources:
                context.add_preferred_resource(resource)
        
        # Return the updated context
        return AvatarContextResponse(**avatar_service.get_progress_summary(user_id=current_user.id))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating avatar context: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating avatar context"
        )


@router.post("/classroom/lesson", response_model=Dict[str, Any])
async def generate_lesson(
    request: LessonRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a complete lesson with all content elements.
    
    Args:
        request: Lesson request
        current_user: Authenticated user
        
    Returns:
        Complete lesson
    """
    try:
        # Validate difficulty
        try:
            difficulty = DifficultyLevel(request.difficulty)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid difficulty level: {request.difficulty}"
            )
        
        # Generate the lesson
        return await lesson_service.generate_complete_lesson(
            subject=request.subject,
            topic=request.topic,
            difficulty=difficulty,
            duration=request.duration,
            user_id=current_user.id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating lesson: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating lesson"
        )


@router.post("/classroom/quiz", response_model=List[Dict[str, Any]])
async def generate_quiz(
    request: QuizRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a quiz for a specific topic.
    
    Args:
        request: Quiz request
        current_user: Authenticated user
        
    Returns:
        List of quiz questions
    """
    try:
        # Validate difficulty
        try:
            difficulty = DifficultyLevel(request.difficulty)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid difficulty level: {request.difficulty}"
            )
        
        # Generate the quiz
        return await lesson_service.generate_quiz_for_topic(
            subject=request.subject,
            topic=request.topic,
            difficulty=difficulty,
            num_questions=request.num_questions,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating quiz: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating quiz"
        )


@router.post("/classroom/curriculum", response_model=Dict[str, Any])
async def generate_curriculum(
    request: CurriculumRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a complete curriculum with modules and lessons.
    
    Args:
        request: Curriculum request
        current_user: Authenticated user
        
    Returns:
        Complete curriculum
    """
    try:
        # Validate difficulty
        try:
            difficulty = DifficultyLevel(request.difficulty)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid difficulty level: {request.difficulty}"
            )
        
        # Validate learning style
        learning_style = None
        if request.learning_style:
            try:
                learning_style = LearningStyle(request.learning_style)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid learning style: {request.learning_style}"
                )
        
        # Validate sequence type
        try:
            sequence_type = ContentSequenceType(request.sequence_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sequence type: {request.sequence_type}"
            )
        
        # Generate the curriculum
        return await content_assembly_service.generate_curriculum(
            subject=request.subject,
            topics=request.topics,
            difficulty=difficulty,
            learning_style=learning_style,
            user_id=current_user.id,
            sequence_type=sequence_type,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating curriculum: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating curriculum"
        )


@router.post("/classroom/learning-pathway", response_model=Dict[str, Any])
async def generate_learning_pathway(
    request: LearningPathwayRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a learning pathway from starting to target level.
    
    Args:
        request: Learning pathway request
        current_user: Authenticated user
        
    Returns:
        Learning pathway
    """
    try:
        # Validate levels
        try:
            starting_level = DifficultyLevel(request.starting_level)
            target_level = DifficultyLevel(request.target_level)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid difficulty level: {str(e)}"
            )
        
        # Generate the learning pathway
        return await content_assembly_service.generate_learning_pathway(
            subject=request.subject,
            starting_level=starting_level,
            target_level=target_level,
            user_id=current_user.id,
            include_external_content=request.include_external_content,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating learning pathway: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating learning pathway"
        )


@router.post("/content/search", response_model=Dict[str, List[Dict[str, Any]]])
async def search_external_content(
    request: ContentSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Search for external educational content.
    
    Args:
        request: Content search request
        current_user: Authenticated user
        
    Returns:
        External content search results
    """
    try:
        # Validate content types
        valid_content_types = ["video", "book", "course", "podcast"]
        for content_type in request.content_types:
            if content_type not in valid_content_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid content type: {content_type}"
                )
        
        # Search for content
        content = await content_retrieval_service.search_all_sources(
            query=request.query,
            content_filters=None,  # No filters for now
            max_results=request.max_results_per_type,
            safe_search=request.safe_search,
        )
        
        # Convert to serializable format
        return {
            content_type: [item.dict() for item in items]
            for content_type, items in content.items()
            if items and content_type in request.content_types
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching content"
        )


@router.post("/classroom/spaced-repetition", response_model=Dict[str, Any])
async def create_spaced_repetition_schedule(
    curriculum_id: str = Query(..., description="ID of the curriculum"),
    duration_days: int = Query(30, description="Duration in days"),
    sessions_per_week: int = Query(3, description="Sessions per week"),
    current_user: User = Depends(get_current_user),
):
    """
    Create a spaced repetition schedule for a curriculum.
    
    Args:
        curriculum_id: ID of the curriculum
        duration_days: Duration in days
        sessions_per_week: Number of sessions per week
        current_user: Authenticated user
        
    Returns:
        Spaced repetition schedule
    """
    try:
        # In a real implementation, you would fetch the curriculum from a database
        # For now, we'll mock this
        curriculum = {
            "id": curriculum_id,
            "modules": [
                {
                    "id": "module_1",
                    "title": "Introduction",
                    "lessons": [
                        {"lesson_id": "lesson_1", "title": "Basics"}
                    ]
                },
                {
                    "id": "module_2",
                    "title": "Intermediate",
                    "lessons": [
                        {"lesson_id": "lesson_2", "title": "Advanced concepts"}
                    ]
                }
            ]
        }
        
        # Create the spaced repetition schedule
        return await content_assembly_service.schedule_spaced_repetition(
            curriculum=curriculum,
            duration_days=duration_days,
            sessions_per_week=sessions_per_week,
            user_id=current_user.id, # Added user_id
        )
        
    except Exception as e:
        logger.error(f"Error creating spaced repetition schedule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating spaced repetition schedule"
        )
