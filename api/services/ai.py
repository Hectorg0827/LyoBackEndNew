"""
AI service.

This module provides services for AI operations such as chat and course generation.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Union

import httpx
from fastapi import Depends, HTTPException, status

from api.core.config import settings
from api.db.firestore import db
from api.db.redis import cache
from api.schemas.ai import (
    ChatMessage,
    ChatRequest,
    ChatStreamResponse,
    CourseRequest,
    CourseResponse,
    ResourceType,
    CourseModule,
    CourseResource,
)
from api.schemas.content import (
    ExternalBook,
    ExternalCourse,
    ExternalPodcast,
    ExternalVideo,
)
from api.services.content import ContentService

logger = logging.getLogger(__name__)


class AIService:
    """AI service."""
    
    def __init__(self, content_service: ContentService = Depends()):
        """
        Initialize AI service.
        
        Args:
            content_service: Content service
        """
        self.content_service = content_service
        self.http_client = httpx.AsyncClient(timeout=60.0)
    
    async def __del__(self):
        """Cleanup resources."""
        await self.http_client.aclose()
    
    async def chat(
        self, user_id: str, request: ChatRequest
    ) -> AsyncGenerator[ChatStreamResponse, None]:
        """
        Chat with avatar using Gemma 3.
        
        Args:
            user_id: User ID
            request: Chat request
            
        Yields:
            ChatStreamResponse: Stream of responses
            
        Raises:
            HTTPException: On error
        """
        try:
            # Save or get conversation history
            conversation_id = request.conversation_id or f"conv_{uuid.uuid4()}"
            history = request.history or []
            
            if not history:
                # Get history from Firestore if conversation ID provided
                if request.conversation_id:
                    conv_ref = db.collection("conversations").document(request.conversation_id)
                    conv_doc = await conv_ref.get()
                    if conv_doc.exists:
                        conv_data = conv_doc.to_dict()
                        history = [ChatMessage.model_validate(msg) for msg in conv_data.get("messages", [])]
            
            # Prepare prompt with history
            system_prompt = f"""You are Lyo, a friendly and helpful AI learning assistant. 
            You give concise, accurate, and friendly responses.
            Use language: {request.lang or 'en-US'}"""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add history
            for msg in history:
                messages.append({"role": msg.role, "content": msg.content})
            
            # Add current prompt
            messages.append({"role": "user", "content": request.prompt})
            
            # Make request to avatar service
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"http://{settings.AVATAR_SERVICE_URL}/v1/chat/completions",
                    json={
                        "model": "gemma-3",
                        "messages": messages,
                        "stream": True,
                        "temperature": 0.7,
                        "max_tokens": 800,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=120.0,
                )
                
                response.raise_for_status()
                full_response = ""
                
                # Stream response
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    # Handle SSE format
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        
                        # End of stream
                        if data == "[DONE]":
                            yield ChatStreamResponse(text="", done=True)
                            break
                        
                        try:
                            data_json = json.loads(data)
                            delta = data_json.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            
                            if content:
                                full_response += content
                                yield ChatStreamResponse(text=content, done=False)
                        except json.JSONDecodeError:
                            continue
            
            # Save conversation history
            if full_response:
                # Append messages to history
                history.append(ChatMessage(role="user", content=request.prompt))
                history.append(ChatMessage(role="assistant", content=full_response))
                
                # Save to Firestore
                await db.collection("conversations").document(conversation_id).set({
                    "user_id": user_id,
                    "messages": [msg.model_dump() for msg in history],
                    "updated_at": datetime.utcnow(),
                    "created_at": datetime.utcnow(),
                }, merge=True)
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in chat: {e}")
            yield ChatStreamResponse(
                text=f"Sorry, I encountered a problem: {str(e)}", done=True
            )
        
        except httpx.RequestError as e:
            logger.error(f"Request error in chat: {e}")
            yield ChatStreamResponse(
                text="Sorry, I couldn't connect to the avatar service.", done=True
            )
        
        except Exception as e:
            logger.exception(f"Error in chat: {e}")
            yield ChatStreamResponse(
                text="Sorry, an unexpected error occurred.", done=True
            )
    
    async def generate_course(
        self, user_id: str, request: CourseRequest
    ) -> CourseResponse:
        """
        Generate course based on topic.
        
        Args:
            user_id: User ID
            request: Course request
            
        Returns:
            CourseResponse: Generated course
            
        Raises:
            HTTPException: On error
        """
        try:
            # Normalize formats
            formats = request.formats or [
                ResourceType.BOOK,
                ResourceType.VIDEO,
                ResourceType.PODCAST,
                ResourceType.ARTICLE,
            ]
            
            # Search for external content based on formats
            external_content = {}
            tasks = []
            
            if ResourceType.BOOK in formats:
                tasks.append(self.content_service.search_books(request.topic))
            
            if ResourceType.VIDEO in formats:
                tasks.append(self.content_service.search_videos(request.topic))
                
            if ResourceType.PODCAST in formats:
                tasks.append(self.content_service.search_podcasts(request.topic))
                
            if ResourceType.COURSE in formats:
                tasks.append(self.content_service.search_courses(request.topic))
            
            # Execute search tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            content_resources = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in content search: {result}")
                    continue
                
                # Convert external content to course resources
                if i == 0 and ResourceType.BOOK in formats:  # Books
                    for book in result:
                        content_resources.append(CourseResource(
                            type=ResourceType.BOOK,
                            title=book.title,
                            url=book.info_link,
                            description=book.description,
                            author=", ".join(book.authors) if book.authors else None,
                            image_url=book.image_url,
                        ))
                
                elif i == 1 and ResourceType.VIDEO in formats:  # Videos
                    for video in result:
                        content_resources.append(CourseResource(
                            type=ResourceType.VIDEO,
                            title=video.title,
                            url=video.video_url,
                            description=video.description,
                            author=video.channel,
                            image_url=video.thumbnail_url,
                            duration=int(video.duration.total_seconds() / 60) if hasattr(video.duration, "total_seconds") else None,
                        ))
                
                elif i == 2 and ResourceType.PODCAST in formats:  # Podcasts
                    for podcast in result:
                        content_resources.append(CourseResource(
                            type=ResourceType.PODCAST,
                            title=podcast.title,
                            url=podcast.audio_url,
                            description=podcast.description,
                            author=podcast.author,
                            image_url=podcast.image_url,
                            duration=int(podcast.duration / 60) if podcast.duration else None,
                        ))
                
                elif i == 3 and ResourceType.COURSE in formats:  # Courses
                    for course in result:
                        content_resources.append(CourseResource(
                            type=ResourceType.COURSE,
                            title=course.title,
                            url=course.url,
                            description=course.description,
                            author=course.instructor,
                            image_url=course.image_url,
                            duration=course.duration,
                        ))
            
            # Generate course outline with AI
            course_modules = await self._generate_course_outline(
                request.topic,
                content_resources,
                request.depth,
                request.lang or "en-US",
            )
            
            # Create course
            now = datetime.utcnow()
            course_id = str(uuid.uuid4())
            
            course = {
                "id": course_id,
                "title": f"Course on {request.topic}",
                "description": f"A {['beginner', 'intermediate', 'advanced', 'expert', 'master'][request.depth-1]} level course on {request.topic}",
                "modules": [module.model_dump() for module in course_modules],
                "created_at": now,
                "updated_at": now,
                "creator_id": user_id,
                "lang": request.lang or "en-US",
            }
            
            # Save to Firestore
            await db.collection("courses").document(course_id).set(course)
            
            # Return response
            return CourseResponse(**course)
        
        except Exception as e:
            logger.exception(f"Error generating course: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate course: {str(e)}",
            )
    
    async def _generate_course_outline(
        self,
        topic: str,
        resources: List[CourseResource],
        depth: int,
        lang: str,
    ) -> List[CourseModule]:
        """
        Generate course outline using AI.
        
        Args:
            topic: Course topic
            resources: Available resources
            depth: Course depth (1-5)
            lang: Language code
            
        Returns:
            List[CourseModule]: List of course modules
        """
        try:
            # In a real implementation, this would use a separate AI service
            # For now, we'll create a simple simulated outline based on resources
            
            # Group resources by type
            resources_by_type = {}
            for resource in resources:
                if resource.type not in resources_by_type:
                    resources_by_type[resource.type] = []
                resources_by_type[resource.type].append(resource)
            
            # Create modules (in a real implementation, these would be determined by AI)
            modules = []
            
            # Basics module
            basics_resources = []
            for resource_type in [ResourceType.VIDEO, ResourceType.ARTICLE]:
                if resource_type in resources_by_type and resources_by_type[resource_type]:
                    # Get first 2 resources of each type
                    basics_resources.extend(resources_by_type[resource_type][:2])
                    resources_by_type[resource_type] = resources_by_type[resource_type][2:]
            
            if basics_resources:
                modules.append(CourseModule(
                    title=f"Basics of {topic}",
                    description=f"Introduction to {topic} for beginners",
                    resources=basics_resources,
                    order=1,
                ))
            
            # Core concepts module
            core_resources = []
            for resource_type in [ResourceType.BOOK, ResourceType.COURSE]:
                if resource_type in resources_by_type and resources_by_type[resource_type]:
                    # Get next 2 resources of each type
                    core_resources.extend(resources_by_type[resource_type][:2])
                    resources_by_type[resource_type] = resources_by_type[resource_type][2:]
            
            if core_resources:
                modules.append(CourseModule(
                    title=f"Core Concepts of {topic}",
                    description=f"Essential knowledge and concepts in {topic}",
                    resources=core_resources,
                    order=2,
                ))
            
            # Advanced module
            advanced_resources = []
            for resource_type, type_resources in resources_by_type.items():
                # Get remaining resources, up to 3 of each type
                advanced_resources.extend(type_resources[:3])
                resources_by_type[resource_type] = type_resources[3:]
            
            if depth >= 3 and advanced_resources:
                modules.append(CourseModule(
                    title=f"Advanced {topic}",
                    description=f"In-depth study of {topic} for experienced learners",
                    resources=advanced_resources,
                    order=3,
                ))
            
            # Additional modules for remaining resources
            remaining_resources = []
            for type_resources in resources_by_type.values():
                remaining_resources.extend(type_resources)
            
            if depth >= 4 and remaining_resources:
                # Split remaining resources into practice and mastery
                mid = len(remaining_resources) // 2
                practice_resources = remaining_resources[:mid]
                mastery_resources = remaining_resources[mid:]
                
                if practice_resources:
                    modules.append(CourseModule(
                        title=f"Practical {topic}",
                        description=f"Practical applications and projects for {topic}",
                        resources=practice_resources,
                        order=4,
                    ))
                
                if depth >= 5 and mastery_resources:
                    modules.append(CourseModule(
                        title=f"Mastering {topic}",
                        description=f"Expert-level content and resources for mastering {topic}",
                        resources=mastery_resources,
                        order=5,
                    ))
            
            return modules
        
        except Exception as e:
            logger.exception(f"Error generating course outline: {e}")
            # Return a minimal outline
            return [
                CourseModule(
                    title=f"Introduction to {topic}",
                    description=f"Basic introduction to {topic}",
                    resources=resources[:5] if resources else [],
                    order=1,
                ),
            ]
    
    async def get_course(self, course_id: str, user_id: Optional[str] = None) -> CourseResponse:
        """
        Get course by ID.
        
        Args:
            course_id: Course ID
            user_id: User ID (for access control)
            
        Returns:
            CourseResponse: Course
            
        Raises:
            HTTPException: If course not found or not accessible
        """
        try:
            # Get course from Firestore
            course_ref = db.collection("courses").document(course_id)
            course_doc = await course_ref.get()
            
            if not course_doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course not found",
                )
            
            course_data = course_doc.to_dict()
            
            # Check access (if user_id provided)
            if user_id and course_data.get("creator_id") != user_id:
                # In a real implementation, check if course is public or shared
                pass
            
            return CourseResponse(**course_data)
        
        except HTTPException:
            raise
        
        except Exception as e:
            logger.exception(f"Error getting course: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get course: {str(e)}",
            )
    
    async def update_course(
        self, course_id: str, user_id: str, updates: Dict
    ) -> CourseResponse:
        """
        Update course.
        
        Args:
            course_id: Course ID
            user_id: User ID
            updates: Updates to apply
            
        Returns:
            CourseResponse: Updated course
            
        Raises:
            HTTPException: If course not found or not accessible
        """
        try:
            # Get course from Firestore
            course_ref = db.collection("courses").document(course_id)
            course_doc = await course_ref.get()
            
            if not course_doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course not found",
                )
            
            course_data = course_doc.to_dict()
            
            # Check access
            if course_data.get("creator_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update this course",
                )
            
            # Apply updates
            for key, value in updates.items():
                if key in ["title", "description", "modules"]:
                    course_data[key] = value
            
            course_data["updated_at"] = datetime.utcnow()
            
            # Save to Firestore
            await course_ref.set(course_data, merge=True)
            
            return CourseResponse(**course_data)
        
        except HTTPException:
            raise
        
        except Exception as e:
            logger.exception(f"Error updating course: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update course: {str(e)}",
            )
