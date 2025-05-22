"""
Content moderation module.

This module provides utilities for moderating content, both user-generated and AI-generated.
"""
import logging
import re
from typing import Dict, List, Optional, Tuple, Union, Any

from api.core.ai_config import ai_config
from api.core.resource_manager import ai_resource_manager
from api.core.tiered_computation import cached_result

logger = logging.getLogger(__name__)


class ContentModerator:
    """Content moderation system for AI-generated and user content."""
    
    def __init__(self):
        """Initialize the content moderator."""
        self.toxic_patterns = [
            re.compile(r'\b(hate|racial slur|violent)\b', re.IGNORECASE),
            # Add more patterns based on your moderation needs
        ]
    
    @cached_result(ttl_key="content_analysis")
    async def check_text_content(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], float]:
        """
        Check if text content violates content policies.
        
        Args:
            text: Text content to check
            context: Additional context about the content
            
        Returns:
            Tuple containing:
            - bool: True if content is safe, False otherwise
            - Optional[str]: Reason if content is unsafe
            - float: Confidence score (0-1)
        """
        # Skip moderation if disabled
        if not ai_config.content_moderation_enabled:
            return True, None, 1.0
            
        # Simple pattern-based check as a quick first pass
        for pattern in self.toxic_patterns:
            if pattern.search(text):
                return False, "Content contains prohibited language", 0.9
        
        # For longer or more complex content, use the AI model
        if len(text) > 50:
            try:
                # Use the resource manager to properly manage the model lifecycle
                async with ai_resource_manager.managed_resource(
                    "model", 
                    ai_config.models.content_moderation["text"]
                ) as model:
                    # Perform moderation check
                    result = await model.analyze(
                        text=text,
                        context=context or {},
                        threshold=ai_config.content_moderation_threshold
                    )
                    
                    # Process result
                    is_safe = result["is_safe"]
                    reason = result.get("reason")
                    confidence = result.get("confidence", 0.5)
                    
                    if not is_safe:
                        logger.warning(f"Content moderation triggered: {reason}")
                        
                    return is_safe, reason, confidence
            except Exception as e:
                logger.error(f"Error during content moderation: {str(e)}")
                # Fall back to allowing content in case of errors
                # In a real system, you might want a different policy based on context
                return True, None, 0.5
        
        # Default to safe for short content that passed pattern checks
        return True, None, 1.0
    
    @cached_result(ttl_key="content_analysis")
    async def check_image_content(
        self, image_url: str, context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], float]:
        """
        Check if image content violates content policies.
        
        Args:
            image_url: URL of image to check
            context: Additional context about the content
            
        Returns:
            Tuple containing:
            - bool: True if content is safe, False otherwise
            - Optional[str]: Reason if content is unsafe
            - float: Confidence score (0-1)
        """
        # Skip moderation if disabled
        if not ai_config.content_moderation_enabled:
            return True, None, 1.0
            
        try:
            # Use the resource manager to properly manage the model lifecycle
            async with ai_resource_manager.managed_resource(
                "model", 
                ai_config.models.content_moderation["image"]
            ) as model:
                # Perform moderation check
                result = await model.analyze(
                    image_url=image_url,
                    context=context or {},
                    threshold=ai_config.content_moderation_threshold
                )
                
                # Process result
                is_safe = result["is_safe"]
                reason = result.get("reason")
                confidence = result.get("confidence", 0.5)
                
                if not is_safe:
                    logger.warning(f"Image moderation triggered: {reason}, URL: {image_url}")
                    
                return is_safe, reason, confidence
        except Exception as e:
            logger.error(f"Error during image content moderation: {str(e)}")
            # Fall back to allowing content in case of errors
            # In a real system, you might want a different policy based on context
            return True, None, 0.5
    
    async def moderate_ai_response(
        self, response: str, context: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """
        Moderate and potentially filter AI-generated responses.
        
        Args:
            response: AI-generated response text
            context: Context of the generation
            
        Returns:
            Tuple containing:
            - str: Moderated response text (original or modified)
            - bool: Whether moderation was applied
        """
        is_safe, reason, _ = await self.check_text_content(
            response, 
            context={"source": "ai_generated", **context}
        )
        
        if not is_safe:
            logger.warning(
                f"AI response moderated: {reason}",
                extra={
                    "original_text": response,
                    "reason": reason,
                    "context": context
                }
            )
            return "I'm sorry, I can't provide that content.", True
            
        return response, False
    
    async def check_user_content(
        self, content_type: str, content: Union[str, Dict[str, Any]], user_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check user-generated content for policy violations.
        
        Args:
            content_type: Type of content (e.g., "post", "comment", "image")
            content: Content to check (text or metadata with URLs)
            user_id: ID of the user who generated the content
            
        Returns:
            Tuple containing:
            - bool: True if content is allowed, False if it violates policies
            - Optional[str]: Reason for rejection if content is rejected
        """
        context = {"source": "user_generated", "content_type": content_type}
        if user_id:
            context["user_id"] = user_id
            
        # For text content
        if isinstance(content, str):
            is_safe, reason, _ = await self.check_text_content(content, context)
            return is_safe, reason
            
        # For structured content
        elif isinstance(content, dict):
            # Check text fields
            text_fields = []
            for field in ["text", "title", "description", "caption"]:
                if field in content and isinstance(content[field], str):
                    text_fields.append(content[field])
            
            # Concatenate text fields
            if text_fields:
                combined_text = " ".join(text_fields)
                is_safe, reason, _ = await self.check_text_content(combined_text, context)
                if not is_safe:
                    return False, reason
            
            # Check image URLs
            image_fields = []
            for field in ["image_url", "media_url", "thumbnail_url"]:
                if field in content and isinstance(content[field], str):
                    image_fields.append(content[field])
            
            # Check each image
            for image_url in image_fields:
                is_safe, reason, _ = await self.check_image_content(image_url, context)
                if not is_safe:
                    return False, reason
        
        # Default to allowing content
        return True, None


# Create a singleton instance
content_moderator = ContentModerator()
