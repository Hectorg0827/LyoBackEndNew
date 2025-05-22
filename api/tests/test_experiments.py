"""
Tests for A/B testing experiments.

This module contains tests for the A/B testing experiment functionality.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from api.core.experiments import (
    ABExperiment,
    experiment_manager,
    experiment
)
from api.core.ai_config import ai_config


def test_get_variant_consistent():
    """Test that variant assignment is consistent for the same user and experiment."""
    # Register a test experiment
    test_experiment = ABExperiment(
        name="test_experiment",
        variants={
            "control": {"algorithm": "baseline"},
            "treatment": {"algorithm": "new_algorithm"},
        }
    )
    experiment_manager.register_experiment(test_experiment)
    
    # Get variant for a user
    variant1 = experiment_manager.get_variant("test_experiment", "user123")
    variant2 = experiment_manager.get_variant("test_experiment", "user123")
    
    # Same user should get the same variant
    assert variant1 == variant2
    
    # Different users should get potentially different variants
    # Note: This could randomly fail with small probability, but it's unlikely
    different_variants_found = False
    for i in range(10):
        user_id = f"user{i}"
        variant = experiment_manager.get_variant("test_experiment", user_id)
        if variant != variant1:
            different_variants_found = True
            break
    
    assert different_variants_found, "Expected different variants for different users"


def test_experiment_disabled():
    """Test that experiments can be disabled."""
    # Register a test experiment
    test_experiment = ABExperiment(
        name="disabled_experiment",
        variants={
            "control": {"algorithm": "baseline"},
            "treatment": {"algorithm": "new_algorithm"},
        }
    )
    experiment_manager.register_experiment(test_experiment)
    
    # Enable experiments
    original_enabled = ai_config.enable_experiments
    ai_config.enable_experiments = True
    
    # Variant should be one of the defined variants
    variant_enabled = experiment_manager.get_variant("disabled_experiment", "test_user")
    assert variant_enabled in ["control", "treatment"]
    
    # Disable experiments
    ai_config.enable_experiments = False
    
    # Variant should be "default" when disabled
    variant_disabled = experiment_manager.get_variant("disabled_experiment", "test_user")
    assert variant_disabled == "default"
    
    # Restore original setting
    ai_config.enable_experiments = original_enabled


def test_track_outcome():
    """Test tracking experiment outcomes."""
    # Mock the telemetry function
    with patch("api.core.experiments.recommendation_quality.record") as mock_record:
        # Track an outcome
        experiment_manager.track_outcome(
            "test_experiment",
            "treatment",
            0.95,
            {"session_id": "abc123"}
        )
        
        # Verify telemetry was called
        mock_record.assert_called_once_with(
            0.95,
            {
                "experiment": "test_experiment",
                "variant": "treatment",
                "session_id": "abc123"
            }
        )


@pytest.mark.asyncio
async def test_experiment_decorator():
    """Test the experiment decorator."""
    # Define variant implementations
    async def control_impl(*args, **kwargs):
        return "control_result"
    
    async def treatment_impl(*args, **kwargs):
        return "treatment_result"
    
    # Create a decorated function
    @experiment("recommendation_algo", {"control": control_impl, "treatment": treatment_impl})
    async def get_recommendations(user_id):
        return "default_result"
    
    # Register the experiment
    test_experiment = ABExperiment(
        name="recommendation_algo",
        variants={
            "control": {"algorithm": "baseline"},
            "treatment": {"algorithm": "new_algorithm"},
        }
    )
    experiment_manager.register_experiment(test_experiment)
    
    # Enable experiments
    original_enabled = ai_config.enable_experiments
    ai_config.enable_experiments = True
    
    # Mock the variant selection to control the test
    with patch("api.core.experiments.experiment_manager.get_variant") as mock_get_variant, \
         patch("api.core.experiments.experiment_manager.track_outcome") as mock_track_outcome:
        
        # Test control variant
        mock_get_variant.return_value = "control"
        result = await get_recommendations("user123")
        assert result == "control_result"
        mock_track_outcome.assert_called_once()
        mock_track_outcome.reset_mock()
        
        # Test treatment variant
        mock_get_variant.return_value = "treatment"
        result = await get_recommendations("user123")
        assert result == "treatment_result"
        mock_track_outcome.assert_called_once()
        mock_track_outcome.reset_mock()
        
        # Test default when variant not found
        mock_get_variant.return_value = "non_existent"
        result = await get_recommendations("user123")
        assert result == "default_result"
        mock_track_outcome.assert_called_once()
    
    # Disable experiments and test again
    ai_config.enable_experiments = False
    result = await get_recommendations("user123")
    assert result == "default_result"
    
    # Restore original setting
    ai_config.enable_experiments = original_enabled


@pytest.mark.asyncio
async def test_experiment_decorator_error_handling():
    """Test error handling in the experiment decorator."""
    # Define variant implementations
    async def failing_impl(*args, **kwargs):
        raise ValueError("Experiment failed")
    
    # Create a decorated function
    @experiment("error_test", {"failing": failing_impl})
    async def test_function(user_id):
        return "default_result"
    
    # Register the experiment
    test_experiment = ABExperiment(
        name="error_test",
        variants={
            "failing": {"algorithm": "failing_algorithm"},
        }
    )
    experiment_manager.register_experiment(test_experiment)
    
    # Mock the variant selection to control the test
    with patch("api.core.experiments.experiment_manager.get_variant") as mock_get_variant, \
         patch("api.core.experiments.experiment_manager.track_outcome") as mock_track_outcome:
        
        mock_get_variant.return_value = "failing"
        
        # The function should propagate the error
        with pytest.raises(ValueError):
            await test_function("user123")
        
        # Outcome should be tracked with a failure value
        mock_track_outcome.assert_called_once_with(
            "error_test",
            "failing",
            0.0,  # Failed outcome
            {
                "error": "Experiment failed",
                "user_id": "user123"
            }
        )
