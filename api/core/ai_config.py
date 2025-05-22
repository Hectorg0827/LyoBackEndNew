"""
AI Configuration module.

This module provides configuration settings for AI components.
"""
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AIComputationConfig(BaseModel):
    """Configuration for AI computation tiers."""
    
    enabled: bool = Field(True, description="Whether tiered computation is enabled")
    default_tier: int = Field(1, description="Default computation tier (1=simple, 2=complex)")
    time_between_complex: int = Field(300, description="Seconds between complex computations")
    max_workers: int = Field(4, description="Maximum workers for parallel AI computation")
    cache_ttl: Dict[str, int] = Field(
        default_factory=lambda: {
            "feed_ranking": 60,           # 1 minute for feed ranking
            "recommendations": 300,        # 5 minutes for recommendations
            "embeddings": 86400,          # 24 hours for embeddings
            "content_analysis": 1800,     # 30 minutes for content analysis
        },
        description="TTL in seconds for various AI operation caches"
    )
    computation_thresholds: Dict[str, int] = Field(
        default_factory=lambda: {
            "feed_calculation_ms": 200,    # Max time for feed calculation in milliseconds
            "recommendation_ms": 500,      # Max time for recommendation calculation
            "embedding_ms": 100,           # Max time for embedding calculation
        },
        description="Performance thresholds for AI operations in milliseconds"
    )


class AIModelsConfig(BaseModel):
    """Configuration for AI models."""
    
    feed_ranking: Dict[str, str] = Field(
        default_factory=lambda: {
            "simple": "feed_ranking_simple_v1",
            "complex": "feed_ranking_neural_v2",
        }
    )
    recommendation: Dict[str, str] = Field(
        default_factory=lambda: {
            "simple": "user_rec_collab_v1",
            "complex": "user_rec_neural_v2",
        }
    )
    course_recommendation: Dict[str, str] = Field(
        default_factory=lambda: {
            "simple": "course_rec_rule_v1",
            "complex": "course_rec_skill_v2",
        }
    )
    content_moderation: Dict[str, str] = Field(
        default_factory=lambda: {
            "text": "text_moderation_v1",
            "image": "image_moderation_v1",
        }
    )


class AIConfig(BaseModel):
    """AI Configuration."""
    
    computation: AIComputationConfig = Field(default_factory=AIComputationConfig)
    models: AIModelsConfig = Field(default_factory=AIModelsConfig)
    enable_experiments: bool = Field(True, description="Enable A/B testing experiments")
    content_moderation_enabled: bool = Field(True, description="Enable content moderation")
    content_moderation_threshold: float = Field(0.8, description="Threshold for content moderation")
    cache_enabled: bool = Field(True, description="Enable AI result caching")
    circuit_breaker_timeout: int = Field(60, description="Circuit breaker timeout in seconds")


# Create a singleton instance
ai_config = AIConfig()


def configure_ai(config_dict: Dict[str, Any] = None) -> None:
    """
    Configure AI settings from a dictionary or environment variables.
    
    Args:
        config_dict: Dictionary with configuration values
    """
    global ai_config
    
    if config_dict:
        # Update from dictionary
        ai_config = AIConfig.model_validate(config_dict)
    else:
        # Update from environment variables with prefix AI_
        import os
        
        env_vars = {}
        for key, value in os.environ.items():
            if key.startswith("AI_"):
                # Convert to lowercase and remove prefix
                config_key = key[3:].lower()
                
                # Handle nested keys with double underscore
                if "__" in config_key:
                    parent, child = config_key.split("__", 1)
                    if parent not in env_vars:
                        env_vars[parent] = {}
                    env_vars[parent][child] = value
                else:
                    env_vars[config_key] = value
        
        # Create a new config with environment variables
        if env_vars:
            ai_config = AIConfig.model_validate(env_vars)
