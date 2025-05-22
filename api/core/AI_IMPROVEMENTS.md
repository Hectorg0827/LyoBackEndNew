# Lyo AI System Improvements

This README documents the improvements made to Lyo's AI systems for better error handling, resource management, and performance optimization.

## 1. Error Handling

We've implemented a more robust error handling system for AI components with:

- Dynamic error type registration through `_load_ai_error_types()` in `errors.py`
- Telemetry integration for AI errors with detailed context tracking
- Graceful degradation patterns for AI services

### Usage Example

```python
from api.core.error_utils_ai import graceful_ai_degradation

@graceful_ai_degradation(fallback_value=[])
async def get_recommendations(user_id):
    """
    Gets recommendations with graceful fallback to empty list on error.
    """
    # Implementation here
    return recommendations
```

## 2. Resource Management

We've created a comprehensive `AIResourceManager` that:

- Implements the async context manager pattern for proper resource lifecycle handling
- Tracks all active AI resources with detailed telemetry
- Ensures proper cleanup even when exceptions occur

### Usage Example

```python
from api.core.resource_manager import ai_resource_manager

async def generate_embeddings(text):
    async with ai_resource_manager.managed_resource(
        "embedding", "text_embedder", dimension=512
    ) as model:
        return await model.embed(text)
```

## 3. Tiered Computation

We've implemented a tiered computation strategy to optimize cost and performance:

- Simple vs. complex computation tiers with automatic switching
- Time-based selection strategy to control frequency of complex operations
- Caching decorator for expensive operations with configurable TTL
- Automatic fallback to simpler algorithms on failure

### Usage Example

```python
from api.core.tiered_computation import with_tiered_computation, cached_result

@with_tiered_computation(
    simple_func=simple_recommendation_algo,
    complex_func=neural_recommendation_algo,
    operation_id="user_recommendations"
)
async def get_user_recommendations(user_id):
    """
    Gets user recommendations using the appropriate algorithm.
    The decorator will choose between simple and complex algorithms.
    """
    # Implementation here (fallback implementation)
    return []

@cached_result(ttl_key="recommendations")
async def expensive_embedding_operation(text):
    """This result will be cached based on the input parameters."""
    # Expensive computation here
    return embeddings
```

## 4. Content Moderation

We've implemented a content moderation system that:

- Provides both rule-based and AI-based moderation approaches
- Handles different content types (text, images)
- Integrates with the resource manager for proper model lifecycle
- Includes telemetry and caching for performance

### Usage Example

```python
from api.core.content_moderation import content_moderator

# Check if user content is safe
is_safe, reason = await content_moderator.check_user_content(
    content_type="post",
    content={"text": "Post text", "image_url": "https://example.com/image.jpg"},
    user_id="user123"
)

# Moderate AI-generated responses
safe_response, was_moderated = await content_moderator.moderate_ai_response(
    response="AI response text here",
    context={"intent": "educational"}
)
```

## 5. A/B Testing Framework

We've created a flexible A/B testing framework for algorithm experimentation:

- Deterministic user assignment to variants based on user ID
- Comprehensive outcome tracking with telemetry
- Support for multiple concurrent experiments
- Simple decorator-based implementation

### Usage Example

```python
from api.core.experiments import experiment, ABExperiment, experiment_manager

# Register an experiment
recommendation_experiment = ABExperiment(
    name="recommendation_algo_v2",
    variants={
        "control": {"algorithm": "collaborative_filtering"},
        "treatment": {"algorithm": "neural_embeddings"},
    },
    description="Test neural embeddings against collaborative filtering"
)
experiment_manager.register_experiment(recommendation_experiment)

# Use the experiment decorator
@experiment(
    "recommendation_algo_v2", 
    {
        "control": collaborative_filtering_impl,
        "treatment": neural_embeddings_impl
    }
)
async def get_recommendations(user_id):
    """
    Gets recommendations using the experiment variant assigned to the user.
    """
    # Fallback implementation
    return default_recommendation_algorithm(user_id)
```

## Configuration

All new systems are configurable through the `AIConfig` class in `ai_config.py`. Configuration can be set programmatically or through environment variables:

```python
from api.core.ai_config import configure_ai

# Configure with a dictionary
configure_ai({
    "computation": {
        "default_tier": 1,  # 1=simple, 2=complex
        "time_between_complex": 300  # 5 minutes
    },
    "content_moderation_enabled": True,
    "content_moderation_threshold": 0.8
})

# Or through environment variables:
# AI__COMPUTATION__DEFAULT_TIER=1
# AI__CONTENT_MODERATION_THRESHOLD=0.8
```

## Integration with Existing Systems

To integrate these new components with existing systems, you'll need to:

1. Apply tiered computation to recommendation and feed services
2. Integrate content moderation with user-generated content flows
3. Set up A/B experiments for key algorithms

Please refer to the test files for examples of how to integrate and use these components.
