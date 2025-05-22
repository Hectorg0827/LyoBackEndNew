"""
AI Resource Manager module.

This module provides a central manager for AI resources like models and embeddings 
to ensure proper initialization, sharing, and cleanup of resources.
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Tuple, TypeVar, AsyncGenerator

from api.core.ai_config import ai_config

logger = logging.getLogger(__name__)

# Type variable for resource types
T = TypeVar("T")


async def get_embedding_model(dimension: int = 768, **kwargs) -> Any:
    """
    Get an embedding model resource.
    
    Args:
        dimension: The embedding dimension
        **kwargs: Additional model parameters
        
    Returns:
        The embedding model resource
    """
    # This would typically connect to your embedding model service
    # Implementation depends on your specific embedding model API
    logger.info(f"Initializing embedding model with dimension {dimension}")
    
    # Simulate model initialization
    await asyncio.sleep(0.1)
    
    # Return model instance
    # In a real implementation, this would return an actual model client/interface
    return EmbeddingModelResource(dimension=dimension, **kwargs)


async def get_inference_model(model_name: str, version: str = "v1", **kwargs) -> Any:
    """
    Get an inference model resource.
    
    Args:
        model_name: The name of the model to load
        version: Model version
        **kwargs: Additional model parameters
        
    Returns:
        The inference model resource
    """
    # This would typically connect to your inference model service
    # Implementation depends on your specific model API
    logger.info(f"Initializing inference model {model_name} (v{version})")
    
    # Simulate model initialization
    await asyncio.sleep(0.1)
    
    # Return model instance
    # In a real implementation, this would return an actual model client/interface
    return InferenceModelResource(model_name=model_name, version=version, **kwargs)


class EmbeddingModelResource:
    """Embedding model resource."""
    
    def __init__(self, dimension: int = 768, **kwargs):
        """
        Initialize embedding model resource.
        
        Args:
            dimension: The embedding dimension
            **kwargs: Additional model parameters
        """
        self.dimension = dimension
        self.kwargs = kwargs
        self.resource_id = f"embedding-{dimension}"
        
    async def close(self):
        """Close and release the resources."""
        # In a real implementation, this would release connections, etc.
        logger.info(f"Closing embedding model resource: {self.resource_id}")
        
    async def embed(self, text: str) -> list:
        """
        Generate embeddings for text.
        
        Args:
            text: The text to embed
            
        Returns:
            list: The embedding vector
        """
        # In a real implementation, this would call the actual embedding model
        # Example placeholder implementation
        return [0.0] * self.dimension


class InferenceModelResource:
    """Inference model resource."""
    
    def __init__(self, model_name: str, version: str = "v1", **kwargs):
        """
        Initialize inference model resource.
        
        Args:
            model_name: The name of the model
            version: Model version
            **kwargs: Additional model parameters
        """
        self.model_name = model_name
        self.version = version
        self.kwargs = kwargs
        self.resource_id = f"{model_name}-{version}"
        
    async def close(self):
        """Close and release the resources."""
        # In a real implementation, this would release connections, etc.
        logger.info(f"Closing inference model resource: {self.resource_id}")
        
    async def predict(self, inputs: Any) -> Any:
        """
        Make predictions using the model.
        
        Args:
            inputs: The inputs for prediction
            
        Returns:
            The prediction results
        """
        # In a real implementation, this would call the actual model
        # Example placeholder implementation
        return {"result": "prediction", "model": self.model_name, "version": self.version}


class AIResourceManager:
    """
    AI Resource Manager.
    
    This class provides centralized management for AI resources like models and embeddings
    to ensure proper initialization, sharing, and cleanup of resources.
    """
    
    def __init__(self):
        """Initialize the AI Resource Manager."""
        self.active_resources: Dict[str, Dict[str, Any]] = {}
    
    @asynccontextmanager
    async def managed_resource(
        self, resource_type: str, resource_name: str, **kwargs
    ) -> AsyncGenerator[Any, None]:
        """
        Context manager for AI resources.
        
        Args:
            resource_type: Type of resource (e.g., "embedding", "model")
            resource_name: Name of the resource
            **kwargs: Resource-specific parameters
            
        Yields:
            The requested resource
        """
        resource_key = f"{resource_type}:{resource_name}"
        resource = None
        
        try:
            # Check if we already have this resource
            if resource_key in self.active_resources:
                logger.debug(f"Reusing existing {resource_type} resource: {resource_name}")
                self.active_resources[resource_key]["ref_count"] += 1
                resource = self.active_resources[resource_key]["resource"]
            else:
                # Initialize the appropriate resource
                logger.info(f"Initializing {resource_type} resource: {resource_name}")
                
                if resource_type == "embedding":
                    resource = await get_embedding_model(**kwargs)
                elif resource_type == "model":
                    resource = await get_inference_model(resource_name, **kwargs)
                else:
                    raise ValueError(f"Unknown resource type: {resource_type}")
                
                # Store in active resources
                self.active_resources[resource_key] = {
                    "resource": resource,
                    "ref_count": 1,
                    "created_at": time.time(),
                }
            
            # Yield the resource to the caller
            yield resource
            
        except Exception as e:
            logger.error(f"Error in managed resource {resource_key}: {str(e)}")
            raise
        
        finally:
            # Clean up the resource if needed
            if resource_key in self.active_resources:
                self.active_resources[resource_key]["ref_count"] -= 1
                
                if self.active_resources[resource_key]["ref_count"] <= 0:
                    logger.info(f"Cleaning up {resource_type} resource: {resource_name}"