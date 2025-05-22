"""
Content Assembly module for building educational materials.

This module provides functionality to assemble various content elements
into coherent educational materials such as courses, lessons, and modules.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from api.core.ai_config import ai_config
from api.core.avatar import avatar_service
from api.core.classroom import DifficultyLevel, lesson_service
from api.core.content_moderation import content_moderator
from api.core.content_retrieval import ContentRelevance, content_retrieval_service
from api.core.resource_manager import ai_resource_manager
from api.core.tiered_computation import cached_result, with_tiered_computation

logger = logging.getLogger(__name__)


class LearningStyle(str, Enum):
    """Learning styles for personalized content assembly."""
    
    VISUAL = "visual"
    AUDITORY = "auditory"
    READING = "reading"
    KINESTHETIC = "kinesthetic"
    MIXED = "mixed"


class ContentSequenceType(str, Enum):
    """Types of content sequences."""
    
    LINEAR = "linear"
    BRANCHING = "branching"
    ADAPTIVE = "adaptive"
    PREREQUISITE = "prerequisite"


class ContentAssemblyService:
    """Service for assembling educational content."""
    
    def __init__(self):
        """Initialize the content assembly service."""
        pass
    
    async def generate_curriculum(
        self,
        subject: str,
        topics: List[str],
        difficulty: Union[str, DifficultyLevel] = DifficultyLevel.BEGINNER,
        learning_style: Optional[LearningStyle] = None,
        user_id: Optional[str] = None,
        sequence_type: ContentSequenceType = ContentSequenceType.LINEAR,
    ) -> Dict[str, Any]:
        """
        Generate a curriculum with sequenced content.
        
        Args:
            subject: Main subject area
            topics: List of topics to cover
            difficulty: Difficulty level
            learning_style: Preferred learning style
            user_id: User ID for personalization
            sequence_type: Type of content sequence
            
        Returns:
            Complete curriculum with sequence information
        """
        # Get user context if available for personalization
        user_context_data = None
        if user_id:
            # Fetch richer user context
            user_avatar_context = await avatar_service._load_or_create_context(user_id, None)
            if user_avatar_context:
                user_context_data = user_avatar_context.to_dict()
        
        # Generate curriculum outline
        outline = await self._generate_curriculum_outline(
            subject=subject,
            topics=topics,
            difficulty=difficulty,
            learning_style=learning_style,
            sequence_type=sequence_type,
            user_context=user_context_data, # Use the fetched context dict
        )
        
        # Generate modules for each section
        curriculum_modules = []
        for section in outline["sections"]:
            # Generate a module for this section
            module = await self._generate_module(
                subject=subject,
                title=section["title"],
                topics=section["topics"],
                difficulty=difficulty,
                learning_style=learning_style,
                user_context=user_context_data, # Pass the context dict
            )
            
            curriculum_modules.append(module)
        
        # Assemble the final curriculum
        curriculum = {
            "id": f"curriculum_{uuid.uuid4().hex[:8]}",
            "title": outline["title"],
            "description": outline["description"],
            "subject": subject,
            "difficulty": difficulty.value if isinstance(difficulty, DifficultyLevel) else difficulty,
            "learning_style": learning_style.value if learning_style else None,
            "sequence_type": sequence_type.value,
            "modules": curriculum_modules,
            "estimated_duration": sum(module["estimated_duration"] for module in curriculum_modules),
            "objectives": outline["objectives"],
            "prerequisites": outline["prerequisites"],
            "created_at": datetime.now().isoformat(),
        }
        
        # For adaptive sequences, add recommended paths
        if sequence_type == ContentSequenceType.ADAPTIVE:
            curriculum["adaptive_paths"] = await self._generate_adaptive_paths(
                curriculum=curriculum, 
                user_context=user_context_data
            )
        
        return curriculum
    
    async def _generate_curriculum_outline(
        self,
        subject: str,
        topics: List[str],
        difficulty: Union[str, DifficultyLevel],
        learning_style: Optional[LearningStyle],
        sequence_type: ContentSequenceType,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a curriculum outline.
        
        Args:
            subject: Main subject area
            topics: List of topics to cover
            difficulty: Difficulty level
            learning_style: Preferred learning style
            sequence_type: Type of content sequence
            user_context: User context for personalization
            
        Returns:
            Curriculum outline
        """
        # Use the AI model to generate the curriculum outline
        async with ai_resource_manager.managed_resource(
            "model", "curriculum_planner"
        ) as model:
            outline = await model.generate_curriculum(
                subject=subject,
                topics=topics,
                difficulty=difficulty.value if isinstance(difficulty, DifficultyLevel) else difficulty,
                learning_style=learning_style.value if learning_style else None,
                sequence_type=sequence_type.value,
                user_context=user_context or {},
            )
            
        return outline
    
    async def _generate_module(
        self,
        subject: str,
        title: str,
        topics: List[str],
        difficulty: Union[str, DifficultyLevel],
        learning_style: Optional[LearningStyle],
        user_context: Optional[Dict[str, Any]] = None, # Expecting dict here
    ) -> Dict[str, Any]:
        """
        Generate a module for the curriculum.
        
        Args:
            subject: Main subject area
            title: Module title
            topics: Topics to cover in this module
            difficulty: Difficulty level
            learning_style: Preferred learning style
            user_context: User context for personalization
            
        Returns:
            Module data
        """
        # Generate lessons for each topic
        lessons = []
        for topic in topics:
            # Generate a lesson for this topic
            lesson = await lesson_service.generate_complete_lesson(
                subject=subject,
                topic=topic,
                difficulty=difficulty,
                duration=30,  # 30 minutes default
                user_id=user_context.get("user_id") if user_context else None, # Pass user_id for lesson service to load context
            )
            
            lessons.append(lesson)
        
        # Calculate estimated duration
        total_duration = sum(lesson["estimated_duration"] for lesson in lessons)
        
        # Create the module
        module = {
            "id": f"module_{uuid.uuid4().hex[:8]}",
            "title": title,
            "description": f"A module covering {title} within {subject}",
            "subject": subject,
            "topics": topics,
            "difficulty": difficulty.value if isinstance(difficulty, DifficultyLevel) else difficulty,
            "lessons": lessons,
            "estimated_duration": total_duration,
            "learning_style": learning_style.value if learning_style else None,
            "created_at": datetime.now().isoformat(),
        }
        
        return module
    
    async def _generate_adaptive_paths(
        self,
        curriculum: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate adaptive learning paths for a curriculum.
        
        Args:
            curriculum: Curriculum data
            user_context: User context for personalization
            
        Returns:
            List of adaptive learning paths
        """
        # In a real implementation, this would be much more sophisticated
        # For now, just create a few paths based on difficulty
        
        difficulties = ["beginner", "intermediate", "advanced"]
        current_difficulty = curriculum["difficulty"]
        
        # Create paths based on different difficulties
        paths = []
        for difficulty in difficulties:
            # Skip the current difficulty (that's the default path)
            if difficulty == current_difficulty:
                continue
                
            # Create a path for this difficulty
            path = {
                "id": f"path_{difficulty}_{uuid.uuid4().hex[:8]}",
                "name": f"{difficulty.capitalize()} path",
                "description": f"An {difficulty} path for learning {curriculum['title']}",
                "difficulty": difficulty,
                "module_sequence": [module["id"] for module in curriculum["modules"]],
                "conditions": {
                    "performance_threshold": 0.7 if difficulty == "advanced" else 0.5,
                    "progression_rules": [
                        {"module_id": module["id"], "min_score": 0.6} 
                        for module in curriculum["modules"]
                    ]
                }
            }
            
            paths.append(path)
            
        return paths
    
    @cached_result(ttl_key="content_assembly")
    async def assemble_content_for_topic(
        self,
        topic: str,
        content_types: List[str] = ["video", "book", "course", "podcast"],
        difficulty: Union[str, DifficultyLevel] = DifficultyLevel.BEGINNER,
        max_items_per_type: int = 3,
        user_id: Optional[str] = None, # Added user_id parameter
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Assemble a collection of content for a specific topic.
        
        Args:
            topic: Topic to find content for
            content_types: Types of content to include
            difficulty: Difficulty level
            max_items_per_type: Maximum items for each content type
            user_id: User ID for personalization (new)
            
        Returns:
            Dictionary of content items by type
        """
        user_context_data = None
        if user_id:
            user_avatar_context = await avatar_service._load_or_create_context(user_id, None)
            if user_avatar_context:
                user_context_data = user_avatar_context.to_dict()

        effective_difficulty = difficulty
        if user_context_data:
            learning_prefs = user_context_data.get("learning_preferences", {})
            user_pref_difficulty_str = learning_prefs.get("difficulty_preference")
            if user_pref_difficulty_str:
                try:
                    user_pref_difficulty = DifficultyLevel(user_pref_difficulty_str)
                    # If the provided difficulty is the default (BEGINNER), override with user's preference
                    if difficulty == DifficultyLevel.BEGINNER:
                        effective_difficulty = user_pref_difficulty
                except ValueError:
                    logger.warning(
                        f"Invalid difficulty_preference in user_context for user {user_id}: {user_pref_difficulty_str}"
                    )
        
        results = {}
        
        # Search for content
        all_content = await content_retrieval_service.search_all_sources(
            query=topic,
            content_filters={
                "difficulty": effective_difficulty.value if isinstance(effective_difficulty, DifficultyLevel) else str(effective_difficulty)
            },
            max_results=max_items_per_type,
            safe_search=True
        )
        
        # Process each content type
        for content_type in content_types:
            if content_type == "video" and "videos" in all_content:
                videos = all_content["videos"]
                # Evaluate and sort videos by relevance
                video_data = []
                for video in videos:
                    # Evaluate relevance
                    relevance = await content_retrieval_service.evaluate_content_relevance(
                        content=video,
                        query=topic
                    )
                    
                    # Skip if not relevant enough
                    if relevance == ContentRelevance.UNRELATED:
                        continue
                        
                    video_data.append({
                        "content": video.dict(),
                        "relevance": relevance.value,
                        "type": "video"
                    })
                
                # Sort by relevance
                video_data.sort(key=lambda x: x["relevance"], reverse=True)
                results["videos"] = video_data[:max_items_per_type]
                
            elif content_type == "book" and "books" in all_content:
                books = all_content["books"]
                # Similar process for books
                book_data = []
                for book in books:
                    relevance = await content_retrieval_service.evaluate_content_relevance(
                        content=book,
                        query=topic
                    )
                    
                    if relevance == ContentRelevance.UNRELATED:
                        continue
                        
                    book_data.append({
                        "content": book.dict(),
                        "relevance": relevance.value,
                        "type": "book"
                    })
                
                book_data.sort(key=lambda x: x["relevance"], reverse=True)
                results["books"] = book_data[:max_items_per_type]
                
            elif content_type == "course" and "courses" in all_content:
                courses = all_content["courses"]
                # Process courses
                course_data = []
                for course in courses:
                    relevance = await content_retrieval_service.evaluate_content_relevance(
                        content=course,
                        query=topic
                    )
                    
                    if relevance == ContentRelevance.UNRELATED:
                        continue
                        
                    course_data.append({
                        "content": course.dict(),
                        "relevance": relevance.value,
                        "type": "course"
                    })
                
                course_data.sort(key=lambda x: x["relevance"], reverse=True)
                results["courses"] = course_data[:max_items_per_type]
                
            elif content_type == "podcast" and "podcasts" in all_content:
                podcasts = all_content["podcasts"]
                # Process podcasts
                podcast_data = []
                for podcast in podcasts:
                    relevance = await content_retrieval_service.evaluate_content_relevance(
                        content=podcast,
                        query=topic
                    )
                    
                    if relevance == ContentRelevance.UNRELATED:
                        continue
                        
                    podcast_data.append({
                        "content": podcast.dict(),
                        "relevance": relevance.value,
                        "type": "podcast"
                    })
                
                podcast_data.sort(key=lambda x: x["relevance"], reverse=True)
                results["podcasts"] = podcast_data[:max_items_per_type]
        
        return results
    
    async def generate_learning_pathway(
        self,
        subject: str,
        starting_level: Union[str, DifficultyLevel],
        target_level: Union[str, DifficultyLevel],
        user_id: Optional[str] = None,
        include_external_content: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a learning pathway from starting to target level.
        
        Args:
            subject: Subject area
            starting_level: User's current level
            target_level: Target proficiency level
            user_id: User ID for personalization
            include_external_content: Whether to include external content
            
        Returns:
            Learning pathway with stages and content
        """
        # Convert string difficulties to enum if needed
        if isinstance(starting_level, str):
            starting_level = DifficultyLevel(starting_level)
            
        if isinstance(target_level, str):
            target_level = DifficultyLevel(target_level)
            
        # Get user context if available
        user_context_data = None
        if user_id:
            # Fetch richer user context
            user_avatar_context = await avatar_service._load_or_create_context(user_id, None)
            if user_avatar_context:
                user_context_data = user_avatar_context.to_dict()
            
        # Generate pathway structure
        async with ai_resource_manager.managed_resource(
            "model", "pathway_generator"
        ) as model:
            pathway = await model.generate_pathway(
                subject=subject,
                starting_level=starting_level.value,
                target_level=target_level.value,
                user_context=user_context_data or {}, # Pass the fetched context dict
            )
            
        # For each stage, create content
        for stage in pathway["stages"]:
            # Generate a lesson for this stage
            stage_topic = stage["topic"]
            
            # Generate lesson
            lesson = await lesson_service.generate_complete_lesson(
                subject=subject,
                topic=stage_topic,
                difficulty=stage["difficulty"],
                duration=45,  # 45 minutes default
                user_id=user_id,
            )
            
            stage["lesson"] = lesson
            
            # Add external content if requested
            if include_external_content:
                # Default content types
                preferred_content_types = ["video", "book"]
                if user_context_data:
                    learning_prefs = user_context_data.get("learning_preferences", {})
                    if isinstance(learning_prefs, dict) and learning_prefs.get("preferred_content_types"):
                        custom_types = learning_prefs["preferred_content_types"]
                        if isinstance(custom_types, list) and custom_types:
                            preferred_content_types = custom_types
                            logger.debug(f"Using preferred_content_types for user {user_id}: {preferred_content_types}")

                external_content = await self.assemble_content_for_topic(
                    topic=stage_topic,
                    content_types=preferred_content_types, # Use preferred types
                    difficulty=stage["difficulty"],
                    max_items_per_type=2,  # Limit to 2 per type for brevity
                    user_id=user_id, # Pass user_id for context use in assemble_content_for_topic
                )
                
                stage["external_content"] = external_content
        
        # Add metadata
        pathway["id"] = f"pathway_{uuid.uuid4().hex[:8]}"
        pathway["created_at"] = datetime.now().isoformat()
        
        return pathway
    
    async def schedule_spaced_repetition(
        self,
        curriculum: Dict[str, Any],
        duration_days: int = 30,
        sessions_per_week: int = 3,
        user_id: Optional[str] = None, # Added user_id
    ) -> Dict[str, Any]:
        """
        Create a spaced repetition schedule for a curriculum.
        
        Args:
            curriculum: Curriculum data
            duration_days: Duration in days
            sessions_per_week: Number of sessions per week
            user_id: Optional user ID for personalization (new)
            
        Returns:
            Spaced repetition schedule
        """
        user_context_data = None
        if user_id:
            try:
                user_avatar_context = await avatar_service._load_or_create_context(user_id, None)
                if user_avatar_context:
                    user_context_data = user_avatar_context.to_dict()
            except Exception as e:
                logger.warning(f"Failed to load avatar context for user {user_id} in schedule_spaced_repetition: {e}")

        # Calculate total number of sessions
        total_sessions = (duration_days // 7) * sessions_per_week
        if total_sessions == 0 and duration_days > 0 and sessions_per_week > 0: # Ensure at least one session if duration/s_p_w allow
            total_sessions = 1


        # Get modules from curriculum
        modules = curriculum.get("modules", [])
        if not modules: # If no modules, return an empty schedule
            return {
                "curriculum_id": curriculum.get("id"),
                "duration_days": duration_days,
                "sessions_per_week": sessions_per_week,
                "sessions": [],
                "user_id": user_id,
            }

        schedule = {
            "curriculum_id": curriculum["id"],
            "duration_days": duration_days,
            "sessions_per_week": sessions_per_week,
            "sessions": [],
            "user_id": user_id,
        }
        
        # Initial learning sessions - cover each module once
        current_day = 0
        session_index = 0
        
        # Ensure sessions_per_week is at least 1 to avoid division by zero
        days_between_initial_sessions = 7 // max(1, sessions_per_week)

        for module in modules:
            session_index += 1
            # Ensure current_day calculation is robust
            current_day = (session_index - 1) * days_between_initial_sessions
            if current_day >= duration_days and session_index > 1: # Avoid scheduling initial beyond duration
                logger.warning(f"Initial session for module {module['id']} (day {current_day}) exceeds duration {duration_days}. Skipping further initial sessions.")
                break


            session = {
                "session_id": session_index,
                "day": current_day,
                "type": "initial",
                "module_id": module["id"],
                "module_title": module["title"],
                "activities": []
            }
            
            for lesson in module.get("lessons", []):
                session["activities"].append({
                    "lesson_id": lesson.get("lesson_id") or lesson.get("id"), # Handle both possible keys
                    "lesson_title": lesson["title"],
                    "duration_minutes": 30 
                })
            
            schedule["sessions"].append(session)

        # Create review sessions using SM-2 like principles
        review_count_target = total_sessions - len(schedule["sessions"]) # Recalculate based on actual initial sessions added
        review_sessions_added = 0
        
        if review_count_target > 0 and modules:
            module_review_progress = {}
            for module in modules:
                initial_session = next((s for s in schedule["sessions"] if s["module_id"] == module["id"] and s["type"] == "initial"), None)
                if initial_session: # Only consider modules that had an initial session scheduled
                    module_review_progress[module["id"]] = {
                        "repetition_number": 0, # 0 means 1st review is due
                        "last_scheduled_day": initial_session["day"]
                    }

            # SM-2 like intervals (days after last event). I_1=1, I_2=6, then I_k = I_{k-1}*EF. Using EF approx 2.
            # Intervals for repetition_number 0, 1, 2, 3, 4 (i.e., 1st, 2nd, 3rd, 4th, 5th review)
            sm2_intervals = [1, 6, 12, 24, 48] 

            if user_context_data:
                learning_prefs = user_context_data.get("learning_preferences", {})
                if isinstance(learning_prefs, dict):
                    pace = learning_prefs.get("pace")
                    if pace == "fast":
                        sm2_intervals = [max(1, int(i * 1.25)) for i in sm2_intervals]
                    elif pace == "slow":
                        sm2_intervals = [max(1, int(i * 0.75)) for i in sm2_intervals]
            
            logger.debug(f"Using SM2-like intervals: {sm2_intervals} for user {user_id or 'default'}")

            while review_sessions_added < review_count_target:
                next_review_candidates = []
                for module_id, progress in module_review_progress.items():
                    if progress["repetition_number"] < len(sm2_intervals):
                        interval = sm2_intervals[progress["repetition_number"]]
                        potential_review_day = progress["last_scheduled_day"] + interval
                        if potential_review_day < duration_days:
                            next_review_candidates.append({
                                "module_id": module_id,
                                "review_day": potential_review_day,
                                "repetition_number": progress["repetition_number"]
                            })
                
                if not next_review_candidates:
                    break 

                next_review_candidates.sort(key=lambda x: (x["review_day"], x["repetition_number"]))
                
                chosen_review = next_review_candidates[0]
                module_id_to_review = chosen_review["module_id"]
                review_day = chosen_review["review_day"]
                
                session_index += 1
                module_to_review = next((m for m in modules if m["id"] == module_id_to_review), None)
                if not module_to_review: continue # Should not happen if module_review_progress is sourced from modules

                review_session = {
                    "session_id": session_index,
                    "day": review_day,
                    "type": "review",
                    "module_id": module_id_to_review,
                    "module_title": module_to_review["title"],
                    "activities": []
                }
                
                if module_to_review.get("lessons"):
                    review_lessons = module_to_review["lessons"][:2] 
                    for lesson in review_lessons:
                        review_session["activities"].append({
                            "lesson_id": lesson.get("lesson_id") or lesson.get("id"),
                            "lesson_title": lesson["title"],
                            "type": "quiz",
                            "duration_minutes": 15
                        })
                
                schedule["sessions"].append(review_session)
                
                module_review_progress[module_id_to_review]["last_scheduled_day"] = review_day
                module_review_progress[module_id_to_review]["repetition_number"] += 1
                review_sessions_added += 1
        
        schedule["sessions"].sort(key=lambda x: (x["day"], x.get("session_id", 0))) # Sort by day, then by original order for stability
        
        return schedule


# Create a singleton instance
content_assembly_service = ContentAssemblyService()
