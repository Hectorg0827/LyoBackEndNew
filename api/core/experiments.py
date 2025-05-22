"""
A/B testing framework for algorithm experimentation.

This module provides utilities for running A/B tests on recommendation algorithms.
"""
import functools
import hashlib
import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast

from api.core.ai_config import ai_config
from api.core.telemetry import recommendation_quality

logger = logging.getLogger(__name__)

# Type variable for function return type
T = TypeVar("T")


class ABExperiment:
    """A/B experiment configuration."""
    
    def __init__(
        self,
        name: str,
        variants: Dict[str, Dict[str, Any]],
        description: Optional[str] = None
    ):
        """
        Initialize an A/B experiment.
        
        Args:
            name: Experiment name
            variants: Dictionary of variant configurations
            description: Experiment description
        """
        self.name = name
        self.variants = variants
        self.description = description
        self.start_time = time.time()


class ExperimentManager:
    """Manages A/B tests for AI algorithms."""
    
    def __init__(self):
        self.active_experiments: Dict[str, ABExperiment] = {}
        
    def register_experiment(
        self, 
        experiment: ABExperiment
    ) -> None:
        """
        Register an experiment.
        
        Args:
            experiment: Experiment configuration
        """
        self.active_experiments[experiment.name] = experiment
        logger.info(f"Registered experiment: {experiment.name}")
        
    def get_variant(self, experiment_id: str, user_id: str) -> str:
        """
        Determine which experiment variant to use for a user.
        
        Args:
            experiment_id: Experiment identifier
            user_id: User identifier
            
        Returns:
            str: Variant name
        """
        if not ai_config.enable_experiments:
            return "default"
            
        # Check if experiment exists
        if experiment_id not in self.active_experiments:
            return "default"
            
        # Get variants
        experiment = self.active_experiments[experiment_id]
        variants = list(experiment.variants.keys())
        
        if not variants:
            return "default"
            
        # Use a hash of user ID and experiment ID for deterministic assignment
        hash_input = f"{user_id}:{experiment_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        
        # Distribute users evenly across variants
        variant_index = hash_value % len(variants)
        return variants[variant_index]
    
    def track_outcome(
        self, 
        experiment_id: str, 
        variant: str, 
        outcome: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track experiment outcome.
        
        Args:
            experiment_id: Experiment identifier
            variant: Variant name
            outcome: Outcome value (higher is better)
            metadata: Additional metadata about the outcome
        """
        # Skip if experiments are disabled
        if not ai_config.enable_experiments:
            return
            
        # Track in telemetry
        recommendation_quality.record(
            outcome,
            {
                "experiment": experiment_id,
                "variant": variant,
                **(metadata or {})
            }
        )
        
        logger.info(
            f"Experiment outcome: {experiment_id} - {variant} - {outcome:.2f}",
            extra={
                "experiment_id": experiment_id,
                "variant": variant,
                "outcome": outcome,
                **(metadata or {})
            }
        )


# Create singleton instance
experiment_manager = ExperimentManager()


def experiment(experiment_id: str, variants: Dict[str, Callable[..., T]]):
    """
    Decorator for running A/B test experiments.
    
    Args:
        experiment_id: Experiment identifier
        variants: Dict mapping variant names to functions
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip if experiments are disabled
            if not ai_config.enable_experiments:
                return await func(*args, **kwargs)
                
            # Get the user ID from kwargs or args
            user_id = kwargs.get("user_id")
            if not user_id:
                # Try to get from first parameter if it's a class instance with user_id
                if args and hasattr(args[0], "user_id"):
                    user_id = args[0].user_id
                    
                # Try to get from first parameter of args[1:] if args[0] is self
                elif len(args) > 1 and hasattr(args[1], "id"):
                    user_id = args[1].id
            
            # Default to original function if can't determine user
            if not user_id:
                logger.warning(f"Could not determine user_id for experiment {experiment_id}")
                return await func(*args, **kwargs)
            
            # Determine variant
            variant = experiment_manager.get_variant(experiment_id, user_id)
            
            # Get variant function or default to original
            variant_func = variants.get(variant, func)
            
            # Execute variant and track outcome
            start_time = time.time()
            try:
                result = await variant_func(*args, **kwargs)
                
                # Track execution time as a simple outcome metric
                execution_time = time.time() - start_time
                experiment_manager.track_outcome(
                    experiment_id, 
                    variant, 
                    1.0,  # Default positive outcome
                    {
                        "execution_time": execution_time,
                        "user_id": user_id
                    }
                )
                return result
            except Exception as e:
                # Record failure
                experiment_manager.track_outcome(
                    experiment_id, 
                    variant, 
                    0.0,  # Failed outcome
                    {
                        "error": str(e),
                        "user_id": user_id
                    }
                )
                # Re-raise the exception
                raise
                
        return cast(Callable[..., T], wrapper)
    return decorator


# Example experiment registration
# recommendation_experiment = ABExperiment(
#     name="user_recommendation_algo",
#     variants={
#         "collaborative": {"algorithm": "collaborative_filtering"},
#         "neural": {"algorithm": "neural_embedding"},
#     },
#     description="Compare collaborative filtering vs neural embeddings for user recommendations",
# )
#
# experiment_manager.register_experiment(recommendation_experiment)
