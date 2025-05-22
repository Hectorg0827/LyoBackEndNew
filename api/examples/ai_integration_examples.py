"""
Integration examples for AI system improvements.

This module provides examples of how to integrate the improved AI systems.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional

from api.core.ai_config import ai_config, configure_ai
from api.core.content_moderation import content_moderator
from api.core.experiments import ABExperiment, experiment, experiment_manager
from api.core.resource_manager import ai_resource_manager
from api.core.tiered_computation import (
    with_tiered_computation,
    cached_result,
    ComputationTier,
)


# Example recommendation service with all improvements applied
class EnhancedRecommendationService:
    """
    Recommendation service with all AI improvements applied.
    
    This class demonstrates how to integrate:
    - Resource management
    - Tiered computation
    - Content moderation
    - A/B testing
    - Result caching
    - Error handling
    """
    
    def __init__(self):
        """Initialize recommendation service."""
        # Register A/B test experiments
        self._register_experiments()
    
    def _register_experiments(self):
        """Register A/B test experiments."""
        # User recommendation algorithm experiment
        user_rec_experiment = ABExperiment(
            name="user_recommendation_algo",
            variants={
                "collaborative": {"algorithm": "collaborative_filtering"},
                "neural": {"algorithm": "neural_embedding"},
            },
            description="Compare collaborative filtering vs neural embeddings for user recommendations"
        )
        experiment_manager.register_experiment(user_rec_experiment)
        
        # Feed ranking experiment
        feed_ranking_experiment = ABExperiment(
            name="feed_ranking_algo",
            variants={
                "engagement": {"algorithm": "engagement_based"},
                "personalized": {"algorithm": "personalized_ranking"},
            },
            description="Compare engagement-based vs personalized ranking for feed"
        )
        experiment_manager.register_experiment(feed_ranking_experiment)
    
    @cached_result(ttl_key="recommendations")
    async def get_user_embeddings(self, user_id: str) -> List[float]:
        """
        Get user embeddings for recommendations.
        
        Applies caching for performance optimization.
        
        Args:
            user_id: User ID
            
        Returns:
            User embedding vector
        """
        async with ai_resource_manager.managed_resource(
            "embedding", "user_embedding_model"
        ) as model:
            return await model.embed_user(user_id)
    
    async def _simple_recommendation_algo(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """Simple recommendation algorithm implementation (collaborative filtering)."""
        # Implementation here - simplified version using basic techniques
        return [{"item_id": f"item{i}", "score": 0.9 - (i * 0.1)} for i in range(limit)]
    
    async def _complex_recommendation_algo(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """Complex recommendation algorithm implementation (neural embeddings)."""
        # Get user embeddings
        user_embedding = await self.get_user_embeddings(user_id)
        
        # Use a more sophisticated model
        async with ai_resource_manager.managed_resource(
            "model", ai_config.models.recommendation["complex"]
        ) as model:
            recommendations = await model.recommend(
                user_embedding=user_embedding,
                limit=limit
            )
        
        return recommendations
    
    @experiment("user_recommendation_algo", {
        "collaborative": _simple_recommendation_algo,
        "neural": _complex_recommendation_algo
    })
    @with_tiered_computation(
        simple_func=_simple_recommendation_algo,
        complex_func=_complex_recommendation_algo,
        operation_id="user_recommendations"
    )
    async def get_recommendations(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations for a user.
        
        This method demonstrates integration of:
        - A/B testing through the @experiment decorator
        - Tiered computation through the @with_tiered_computation decorator
        - Resource management (in the algorithm implementations)
        - Caching (in the get_user_embeddings method)
        
        Args:
            user_id: User ID
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended items with scores
        """
        # This is a fallback implementation that would be used if neither
        # the experiment decorator nor the tiered computation selected
        # a specific implementation
        return await self._simple_recommendation_algo(user_id, limit)
    
    async def _moderate_recommendations(
        self, recommendations: List[Dict[str, Any]], user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Apply content moderation to recommendations.
        
        Args:
            recommendations: List of recommendations
            user_id: User ID
            
        Returns:
            Filtered list of recommendations
        """
        filtered_recommendations = []
        
        for item in recommendations:
            # Check if each item passes content moderation
            if "description" in item:
                is_safe, _, _ = await content_moderator.check_text_content(
                    item["description"],
                    {"source": "recommendation", "user_id": user_id}
                )
                
                if is_safe:
                    filtered_recommendations.append(item)
            else:
                # If no content to moderate, include the item
                filtered_recommendations.append(item)
        
        return filtered_recommendations
    
    async def get_safe_recommendations(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get content-moderated recommendations for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of recommendations
            
        Returns:
            List of safe recommendations
        """
        # Get base recommendations
        recommendations = await self.get_recommendations(user_id, limit=limit * 2)
        
        # Apply content moderation if enabled
        if ai_config.content_moderation_enabled:
            filtered = await self._moderate_recommendations(recommendations, user_id)
            
            # If we filtered too many, get more recommendations
            if len(filtered) < limit and len(filtered) < len(recommendations):
                more_recommendations = await self.get_recommendations(
                    user_id, 
                    limit=limit * 2 - len(recommendations)
                )
                more_filtered = await self._moderate_recommendations(more_recommendations, user_id)
                filtered.extend(more_filtered)
            
            return filtered[:limit]
        
        return recommendations[:limit]


# Example AI chat service with moderation
class SafeChatService:
    """
    AI chat service with content moderation.
    
    This class demonstrates content moderation for AI-generated responses.
    """
    
    async def generate_response(self, user_message: str, user_id: str) -> str:
        """
        Generate a moderated AI response to a user message.
        
        Args:
            user_message: User's message
            user_id: User ID
            
        Returns:
            AI-generated and moderated response
        """
        # First check if the user's message is appropriate
        is_safe, reason, _ = await content_moderator.check_text_content(
            user_message,
            {"source": "chat_input", "user_id": user_id}
        )
        
        if not is_safe:
            return f"I'm sorry, but I can't respond to that type of message. {reason}"
        
        # Generate AI response
        async with ai_resource_manager.managed_resource("model", "chat_model") as model:
            ai_response = await model.generate(user_message)
        
        # Moderate the AI-generated response
        safe_response, was_moderated = await content_moderator.moderate_ai_response(
            ai_response, 
            {"user_message": user_message, "user_id": user_id}
        )
        
        return safe_response


# Example of how to configure the systems
async def configure_ai_systems():
    """Configure AI systems based on environment."""
    # Configure AI settings
    configure_ai({
        "computation": {
            "default_tier": ComputationTier.SIMPLE,
            "time_between_complex": 300,  # 5 minutes
            "cache_ttl": {
                "recommendations": 600,  # 10 minutes
                "embeddings": 3600,  # 1 hour
            }
        },
        "enable_experiments": True,
        "content_moderation_enabled": True,
        "content_moderation_threshold": 0.85,
    })
    
    # After configuration, you can instantiate and use the services
    recommendation_service = EnhancedRecommendationService()
    chat_service = SafeChatService()
    
    # Example usage
    recommendations = await recommendation_service.get_safe_recommendations("user123")
    chat_response = await chat_service.generate_response("Hello AI!", "user123")
    
    print(f"Recommendations: {recommendations}")
    print(f"Chat response: {chat_response}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(configure_ai_systems())
