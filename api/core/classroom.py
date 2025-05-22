"""
AI Classroom module for dynamic lesson generation.

This module provides functionality to generate and assemble
educational content for the AI-powered classroom.
"""
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from api.core.ai_config import ai_config
# Ensure AvatarService is imported, and avatar_service (global instance) is available if used as fallback
from api.core.avatar import AvatarService, avatar_service 
from api.core.content_moderation import content_moderator
from api.core.resource_manager import ai_resource_manager
from api.core.tiered_computation import cached_result, with_tiered_computation

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Types of educational content."""
    
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    QUIZ = "quiz"
    EXERCISE = "exercise"
    INFOGRAPHIC = "infographic"
    CODE = "code"


class DifficultyLevel(str, Enum):
    """Difficulty levels for educational content."""
    
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LearningObjective:
    """Learning objective for a lesson or module."""
    
    def __init__(
        self,
        description: str,
        priority: int = 1,  # 1-5, with 1 being highest priority
        completed: bool = False,
    ):
        """
        Initialize a learning objective.
        
        Args:
            description: Description of the objective
            priority: Priority level (1-5)
            completed: Whether the objective is completed
        """
        self.description = description
        self.priority = priority
        self.completed = completed
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "priority": self.priority,
            "completed": self.completed,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningObjective':
        """Create from dictionary."""
        return cls(
            description=data["description"],
            priority=data.get("priority", 1),
            completed=data.get("completed", False),
        )


class ContentElement:
    """Element of educational content."""
    
    def __init__(
        self,
        element_id: str,
        content_type: Union[ContentType, str],
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a content element.
        
        Args:
            element_id: Unique identifier
            content_type: Type of content
            content: Content data
            metadata: Additional metadata
        """
        self.element_id = element_id
        
        if isinstance(content_type, str):
            self.content_type = ContentType(content_type)
        else:
            self.content_type = content_type
            
        self.content = content
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "element_id": self.element_id,
            "content_type": self.content_type.value,
            "content": self.content,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentElement':
        """Create from dictionary."""
        return cls(
            element_id=data["element_id"],
            content_type=data["content_type"],
            content=data["content"],
            metadata=data.get("metadata", {}),
        )


class Lesson:
    """AI-generated or curated lesson."""
    
    def __init__(
        self,
        lesson_id: str,
        title: str,
        subject: str,
        description: str,
        elements: List[ContentElement],
        objectives: List[LearningObjective],
        difficulty: Union[DifficultyLevel, str],
        estimated_duration: int,  # in minutes
        author: str = "Lyo AI",
        tags: Optional[List[str]] = None,
        prerequisites: Optional[List[str]] = None,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None,
    ):
        """
        Initialize a lesson.
        
        Args:
            lesson_id: Unique identifier
            title: Lesson title
            subject: Subject area
            description: Lesson description
            elements: List of content elements
            objectives: List of learning objectives
            difficulty: Difficulty level
            estimated_duration: Estimated duration in minutes
            author: Lesson author
            tags: Subject tags
            prerequisites: Prerequisite lesson IDs
            created_at: Creation timestamp
            updated_at: Last update timestamp
        """
        self.lesson_id = lesson_id
        self.title = title
        self.subject = subject
        self.description = description
        self.elements = elements
        self.objectives = objectives
        
        if isinstance(difficulty, str):
            self.difficulty = DifficultyLevel(difficulty)
        else:
            self.difficulty = difficulty
            
        self.estimated_duration = estimated_duration
        self.author = author
        self.tags = tags or []
        self.prerequisites = prerequisites or []
        self.created_at = created_at or datetime.now().timestamp()
        self.updated_at = updated_at or self.created_at
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lesson_id": self.lesson_id,
            "title": self.title,
            "subject": self.subject,
            "description": self.description,
            "elements": [element.to_dict() for element in self.elements],
            "objectives": [objective.to_dict() for objective in self.objectives],
            "difficulty": self.difficulty.value,
            "estimated_duration": self.estimated_duration,
            "author": self.author,
            "tags": self.tags,
            "prerequisites": self.prerequisites,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lesson':
        """Create from dictionary."""
        return cls(
            lesson_id=data["lesson_id"],
            title=data["title"],
            subject=data["subject"],
            description=data["description"],
            elements=[ContentElement.from_dict(element) for element in data["elements"]],
            objectives=[LearningObjective.from_dict(objective) for objective in data["objectives"]],
            difficulty=data["difficulty"],
            estimated_duration=data["estimated_duration"],
            author=data.get("author", "Lyo AI"),
            tags=data.get("tags", []),
            prerequisites=data.get("prerequisites", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class Module:
    """Collection of lessons forming a coherent educational module."""
    
    def __init__(
        self,
        module_id: str,
        title: str,
        description: str,
        lessons: List[str],  # List of lesson IDs
        difficulty: Union[DifficultyLevel, str],
        estimated_duration: int,  # in minutes
        author: str = "Lyo AI",
        tags: Optional[List[str]] = None,
        prerequisites: Optional[List[str]] = None,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None,
    ):
        """
        Initialize a module.
        
        Args:
            module_id: Unique identifier
            title: Module title
            description: Module description
            lessons: List of lesson IDs
            difficulty: Difficulty level
            estimated_duration: Estimated duration in minutes
            author: Module author
            tags: Subject tags
            prerequisites: Prerequisite module IDs
            created_at: Creation timestamp
            updated_at: Last update timestamp
        """
        self.module_id = module_id
        self.title = title
        self.description = description
        self.lessons = lessons
        
        if isinstance(difficulty, str):
            self.difficulty = DifficultyLevel(difficulty)
        else:
            self.difficulty = difficulty
            
        self.estimated_duration = estimated_duration
        self.author = author
        self.tags = tags or []
        self.prerequisites = prerequisites or []
        self.created_at = created_at or datetime.now().timestamp()
        self.updated_at = updated_at or self.created_at
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "module_id": self.module_id,
            "title": self.title,
            "description": self.description,
            "lessons": self.lessons,
            "difficulty": self.difficulty.value,
            "estimated_duration": self.estimated_duration,
            "author": self.author,
            "tags": self.tags,
            "prerequisites": self.prerequisites,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Module':
        """Create from dictionary."""
        return cls(
            module_id=data["module_id"],
            title=data["title"],
            description=data["description"],
            lessons=data["lessons"],
            difficulty=data["difficulty"],
            estimated_duration=data["estimated_duration"],
            author=data.get("author", "Lyo AI"),
            tags=data.get("tags", []),
            prerequisites=data.get("prerequisites", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class QuizQuestion:
    """Question for a quiz or assessment."""
    
    def __init__(
        self,
        question_id: str,
        question_text: str,
        question_type: str,  # "multiple_choice", "true_false", "short_answer", "code"
        options: Optional[List[str]] = None,  # For multiple choice
        correct_answer: Any = None,
        explanation: Optional[str] = None,
        difficulty: Union[DifficultyLevel, str] = DifficultyLevel.BEGINNER,
        points: int = 1,
    ):
        """
        Initialize a quiz question.
        
        Args:
            question_id: Unique identifier
            question_text: Question text
            question_type: Type of question
            options: List of options for multiple choice
            correct_answer: Correct answer or list of accepted answers
            explanation: Explanation of the answer
            difficulty: Question difficulty
            points: Points for the question
        """
        self.question_id = question_id
        self.question_text = question_text
        self.question_type = question_type
        self.options = options or []
        self.correct_answer = correct_answer
        self.explanation = explanation
        
        if isinstance(difficulty, str):
            self.difficulty = DifficultyLevel(difficulty)
        else:
            self.difficulty = difficulty
            
        self.points = points
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "difficulty": self.difficulty.value,
            "points": self.points,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuizQuestion':
        """Create from dictionary."""
        return cls(
            question_id=data["question_id"],
            question_text=data["question_text"],
            question_type=data["question_type"],
            options=data.get("options", []),
            correct_answer=data.get("correct_answer"),
            explanation=data.get("explanation"),
            difficulty=data.get("difficulty", DifficultyLevel.BEGINNER),
            points=data.get("points", 1),
        )


class LessonGenerationService:
    """Service for generating AI classroom lessons."""
    
    def __init__(self, avatar_service_instance: Optional[AvatarService] = None):
        """Initialize the lesson generation service."""
        # Use the injected avatar_service or the global one (Sourcery: Replace if-expression with `or`)
        self.avatar_service = avatar_service_instance or avatar_service
    
    def _generate_lesson_id(self) -> str:
        """Generate a unique lesson ID."""
        return f"lesson_{uuid.uuid4().hex[:12]}"
    
    def _generate_module_id(self) -> str:
        """Generate a unique module ID."""
        return f"module_{uuid.uuid4().hex[:12]}"
    
    def _generate_element_id(self) -> str:
        """Generate a unique element ID."""
        return f"element_{uuid.uuid4().hex[:8]}"
    
    def _generate_question_id(self) -> str:
        """Generate a unique question ID."""
        return f"question_{uuid.uuid4().hex[:8]}"
    
    async def generate_lesson_outline(
        self,
        subject: str,
        topic: str,
        difficulty: Union[DifficultyLevel, str] = DifficultyLevel.BEGINNER,
        duration: int = 30,  # minutes
        user_context: Optional[Dict[str, Any]] = None, # Keep for direct passing if needed
        user_id: Optional[str] = None # Added for fetching fresh context
    ) -> Dict[str, Any]:
        """
        Generate an outline for a new lesson.
        
        Args:
            subject: Subject area
            topic: Specific topic
            difficulty: Desired difficulty level
            duration: Target duration in minutes
            user_context: Pre-fetched user context (optional)
            user_id: User ID to fetch fresh context for personalization (optional)
            
        Returns:
            Lesson outline
        """
        if isinstance(difficulty, str):
            try:
                difficulty = DifficultyLevel(difficulty)
            except ValueError:
                difficulty = DifficultyLevel.BEGINNER
        
        # Fetch fresh user context if user_id is provided and no pre-fetched context
        effective_user_context = user_context
        if user_id and not effective_user_context:
            try:
                # Load full AvatarContext and convert to dict for personalization
                # This assumes avatar_service has _load_or_create_context method
                # and AvatarContext has to_dict method.
                # This replaces the previous get_progress_summary which might not exist or be suitable.
                context_obj = await self.avatar_service._load_or_create_context(user_id, None) # session_id can be None for general context
                if context_obj:
                    effective_user_context = context_obj.to_dict()
                    logger.info(f"Fetched user context for {user_id} for lesson outline generation.")
                else:
                    effective_user_context = {}
                    logger.warning(f"Could not fetch context for user {user_id}, proceeding without personalization.")
            except Exception as e:
                logger.error(f"Failed to fetch user context for {user_id}: {e}", exc_info=True)
                effective_user_context = {} # Default to empty if fetch fails

        # Use the AI resource manager for model access
        async with ai_resource_manager.managed_resource(
            "model", "lesson_generator"
        ) as model:
            # Generate lesson outline
            # The model.generate_outline should be capable of using learning_style, learning_pace etc.
            # from the user_context.
            outline_params = {
                "subject": subject,
                "topic": topic,
                "difficulty": difficulty.value,
                "duration": duration,
                "user_context": effective_user_context or {} # Ensure it's at least an empty dict
            }
            # Add personalization fields if present in context
            if effective_user_context:
                if "learning_style" in effective_user_context and effective_user_context["learning_style"]:
                    outline_params["learning_style"] = effective_user_context["learning_style"]
                if "learning_pace" in effective_user_context and effective_user_context["learning_pace"]:
                    outline_params["learning_pace"] = effective_user_context["learning_pace"]
                if "strengths" in effective_user_context and effective_user_context["strengths"]:
                    outline_params["user_strengths"] = effective_user_context["strengths"]
                if "areas_for_improvement" in effective_user_context and effective_user_context["areas_for_improvement"]:
                    outline_params["user_weaknesses"] = effective_user_context["areas_for_improvement"]
            
            logger.debug(f"Generating lesson outline with params: {outline_params}")
            outline = await model.generate_outline(**outline_params)
            
        lesson_id = self._generate_lesson_id()
            
        return {
            "lesson_id": lesson_id,
            "title": outline["title"],
            "subject": subject,
            "description": outline["description"],
            "objectives": outline["objectives"],
            "sections": outline["sections"],
            "difficulty": difficulty.value,
            "estimated_duration": duration,
        }
    
    async def generate_content_elements(
        self,
        subject: str,
        topic: str,
        section_title: str,
        element_types: Optional[List[str]] = None,
        difficulty: Union[DifficultyLevel, str] = DifficultyLevel.BEGINNER,
        user_context: Optional[Dict[str, Any]] = None # Added for personalization
    ) -> List[Dict[str, Any]]:
        """
        Generate content elements for a lesson section.
        
        Args:
            subject: Subject area
            topic: Specific topic
            section_title: Title of the section
            element_types: Types of elements to generate
            difficulty: Content difficulty
            user_context: User context for personalization (contains learning_style, pace, etc.)
            
        Returns:
            List of content elements
        """
        if not element_types:
            element_types = ["text", "quiz"]
            
        if isinstance(difficulty, str):
            try:
                difficulty = DifficultyLevel(difficulty)
            except ValueError:
                difficulty = DifficultyLevel.BEGINNER
                
        # Use the AI resource manager for model access
        async with ai_resource_manager.managed_resource(
            "model", "content_generator"
        ) as model:
            # Generate content elements
            # The model.generate_elements should be capable of using learning_style etc.
            # from the user_context.
            generation_params = {
                "subject": subject,
                "topic": topic,
                "section_title": section_title,
                "element_types": element_types,
                "difficulty": difficulty.value,
                "user_context": user_context or {} # Pass user_context
            }
            if user_context: # Add specific personalization fields if available
                if "learning_style" in user_context and user_context["learning_style"]:
                    generation_params["learning_style"] = user_context["learning_style"]
                if "learning_pace" in user_context and user_context["learning_pace"]:
                    generation_params["learning_pace"] = user_context["learning_pace"]

            logger.debug(f"Generating content elements with params: {generation_params}")
            elements = await model.generate_elements(**generation_params)
            
        # Process and transform elements
        processed_elements = []
        for element in elements:
            # Generate a unique ID for each element
            element_id = self._generate_element_id()
            
            # Create a ContentElement
            element_data = {
                "element_id": element_id,
                "content_type": element["type"],
                "content": element["content"],
                "metadata": element.get("metadata", {})
            }
            
            # If it's a quiz, process the questions
            if element["type"] == "quiz":
                questions = []
                for q_data in element["content"]["questions"]:
                    question_id = self._generate_question_id()
                    questions.append({
                        "question_id": question_id,
                        "question_text": q_data["text"],
                        "question_type": q_data["type"],
                        "options": q_data.get("options", []),
                        "correct_answer": q_data.get("correct_answer"),
                        "explanation": q_data.get("explanation"),
                        "difficulty": difficulty.value,
                        "points": q_data.get("points", 1),
                    })
                element_data["content"]["questions"] = questions
                
            processed_elements.append(element_data)
            
        return processed_elements
    
    @cached_result(ttl_key="recommendations") # Consider if user-specific caching is needed
    async def generate_complete_lesson(
        self,
        subject: str,
        topic: str,
        difficulty: Union[DifficultyLevel, str] = DifficultyLevel.BEGINNER,
        duration: int = 30,  # minutes
        user_id: Optional[str] = None, # Keep user_id for fetching context
    ) -> Dict[str, Any]:
        """
        Generate a complete lesson with all content elements.
        
        Args:
            subject: Subject area
            topic: Specific topic
            difficulty: Desired difficulty level
            duration: Target duration in minutes
            user_id: User identifier for personalization
            
        Returns:
            Complete lesson data
        """
        # Get user context if available
        effective_user_context = None
        if user_id:
            try:
                # Use the injected avatar_service instance
                # Load full AvatarContext and convert to dict for personalization
                context_obj = await self.avatar_service._load_or_create_context(user_id, None)
                if context_obj:
                    effective_user_context = context_obj.to_dict()
                    logger.info(f"Fetched user context for {user_id} for complete lesson generation.")
                else:
                    effective_user_context = {}
                    logger.warning(f"Could not fetch context for user {user_id} in generate_complete_lesson, proceeding with less personalization.")
            except Exception as e:
                logger.error(f"Failed to fetch user context for {user_id} in generate_complete_lesson: {e}", exc_info=True)
                effective_user_context = {}

        # Generate lesson outline, passing the fetched user_context
        outline = await self.generate_lesson_outline(
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            duration=duration,
            user_context=effective_user_context # Pass the fetched context directly
            # user_id is not needed here again as context is already fetched
        )
        
        # Generate content for each section
        sections = outline["sections"]
        all_elements = []
        
        for section in sections:
            # Generate content elements for the section, passing user_context
            elements_data = await self.generate_content_elements(
                subject=subject,
                topic=topic, # Should this be section-specific topic or overall lesson topic?
                section_title=section["title"],
                element_types=section.get("element_types", ["text", "quiz"]),
                difficulty=difficulty, # Or section-specific difficulty if outline provides it
                user_context=effective_user_context # Pass the fetched context
            )
            
            # Add elements to the list (Sourcery: Replace a for append loop with list extend)
            all_elements.extend([ContentElement.from_dict(element) for element in elements_data])
                
        # Create learning objectives (Sourcery: Replace a for append loop with list extend/comprehension)
        objectives = [
            LearningObjective(description=obj["description"], priority=obj.get("priority", 1))
            for obj in outline["objectives"]
        ]
                
        # Create the lesson
        lesson = Lesson(
            lesson_id=outline["lesson_id"],
            title=outline["title"],
            subject=outline["subject"],
            description=outline["description"],
            elements=all_elements,
            objectives=objectives,
            difficulty=difficulty,
            estimated_duration=outline["estimated_duration"],
            tags=[topic] + [section["title"] for section in sections],
        )
        
        return lesson.to_dict()
    
    async def generate_quiz_for_topic(
        self,
        subject: str,
        topic: str,
        difficulty: Union[DifficultyLevel, str] = DifficultyLevel.BEGINNER,
        num_questions: int = 5,
        user_context: Optional[Dict[str, Any]] = None # Added for personalization
    ) -> List[Dict[str, Any]]:
        """
        Generate a quiz for a specific topic.
        
        Args:
            subject: Subject area
            topic: Specific topic
            difficulty: Quiz difficulty level
            num_questions: Number of questions
            user_context: User context for personalization (e.g., areas_for_improvement)
            
        Returns:
            List of quiz questions
        """
        if isinstance(difficulty, str):
            try:
                difficulty = DifficultyLevel(difficulty)
            except ValueError:
                difficulty = DifficultyLevel.BEGINNER
                
        # Use the AI resource manager for model access
        async with ai_resource_manager.managed_resource(
            "model", "quiz_generator"
        ) as model:
            # Generate quiz questions
            # The model.generate_quiz should be capable of using user_context
            quiz_params = {
                "subject": subject,
                "topic": topic,
                "difficulty": difficulty.value,
                "num_questions": num_questions,
                "user_context": user_context or {}
            }
            if user_context:
                if "areas_for_improvement" in user_context and user_context["areas_for_improvement"]:
                    quiz_params["focus_areas"] = user_context["areas_for_improvement"]
                if "strengths" in user_context and user_context["strengths"]:
                    quiz_params["avoid_areas"] = user_context["strengths"] # e.g. to not make it too easy

            logger.debug(f"Generating quiz with params: {quiz_params}")
            questions = await model.generate_quiz(**quiz_params)
            
        # Process questions
        processed_questions = []
        for q_data in questions:
            question_id = self._generate_question_id()
            processed_questions.append(QuizQuestion(
                question_id=question_id,
                question_text=q_data["text"],
                question_type=q_data["type"],
                options=q_data.get("options", []),
                correct_answer=q_data.get("correct_answer"),
                explanation=q_data.get("explanation"),
                difficulty=difficulty,
                points=q_data.get("points", 1),
            ).to_dict())
            
        return processed_questions


# Singleton instance - now needs avatar_service injected if not using global
# This might require adjustment depending on how AvatarService is globally managed/accessed
# For now, assume global avatar_service is available or adjust instantiation at application startup.
lesson_service = LessonGenerationService(avatar_service_instance=avatar_service)
