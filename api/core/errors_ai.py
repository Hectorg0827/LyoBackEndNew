"""
AI-specific error handling module.

This module defines custom exceptions for AI-driven features in the application.
"""
from typing import Any, Dict, List, Optional, Union

from api.core.errors import APIError


class AlgorithmError(APIError):
    """Base error for algorithm-related issues."""
    
    def __init__(
        self,
        detail: str = "Algorithm processing error",
        code: str = "algorithm_error",
        algorithm_name: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize algorithm error.
        
        Args:
            detail: Error detail message
            code: Error code
            algorithm_name: Name of the algorithm that failed
            **kwargs: Additional arguments for APIError
        """
        data = kwargs.pop("data", {})
        if algorithm_name:
            data["algorithm_name"] = algorithm_name
        super().__init__(
            status_code=500, detail=detail, code=code, data=data, **kwargs
        )


class RecommendationError(AlgorithmError):
    """Error in recommendation algorithm."""
    
    def __init__(
        self,
        detail: str = "Failed to generate recommendations",
        code: str = "recommendation_error",
        recommendation_type: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize recommendation error.
        
        Args:
            detail: Error detail message
            code: Error code
            recommendation_type: Type of recommendation (e.g., 'user', 'content', 'course')
            **kwargs: Additional arguments for AlgorithmError
        """
        data = kwargs.pop("data", {})
        if recommendation_type:
            data["recommendation_type"] = recommendation_type
        super().__init__(
            detail=detail, code=code, data=data, **kwargs
        )


class FeedProcessingError(AlgorithmError):
    """Error in feed processing algorithm."""
    
    def __init__(
        self,
        detail: str = "Failed to process feed data",
        code: str = "feed_processing_error",
        feed_type: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize feed processing error.
        
        Args:
            detail: Error detail message
            code: Error code
            feed_type: Type of feed (e.g., 'main', 'stories', 'suggested')
            **kwargs: Additional arguments for AlgorithmError
        """
        data = kwargs.pop("data", {})
        if feed_type:
            data["feed_type"] = feed_type
        super().__init__(
            detail=detail, code=code, data=data, **kwargs
        )


class DataProcessingError(APIError):
    """Error in data processing operations."""
    
    def __init__(
        self,
        detail: str = "Data processing error",
        code: str = "data_processing_error",
        data_type: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize data processing error.
        
        Args:
            detail: Error detail message
            code: Error code
            data_type: Type of data being processed
            **kwargs: Additional arguments for APIError
        """
        data = kwargs.pop("data", {})
        if data_type:
            data["data_type"] = data_type
        super().__init__(
            status_code=500, detail=detail, code=code, data=data, **kwargs
        )


class ContentModerationError(APIError):
    """Error in content moderation."""
    
    def __init__(
        self,
        detail: str = "Content moderation error",
        code: str = "content_moderation_error",
        content_type: Optional[str] = None,
        moderation_reason: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize content moderation error.
        
        Args:
            detail: Error detail message
            code: Error code
            content_type: Type of content being moderated
            moderation_reason: Reason for moderation failure
            **kwargs: Additional arguments for APIError
        """
        data = kwargs.pop("data", {})
        if content_type:
            data["content_type"] = content_type
        if moderation_reason:
            data["moderation_reason"] = moderation_reason
        super().__init__(
            status_code=400, detail=detail, code=code, data=data, **kwargs
        )


class AIQuotaExceededError(APIError):
    """Error when AI computation quota is exceeded."""
    
    def __init__(
        self,
        detail: str = "AI computation quota exceeded",
        code: str = "ai_quota_exceeded",
        quota_type: Optional[str] = None,
        reset_time: Optional[int] = None,
        **kwargs,
    ):
        """
        Initialize AI quota exceeded error.
        
        Args:
            detail: Error detail message
            code: Error code
            quota_type: Type of quota exceeded
            reset_time: Time in seconds when quota will reset
            **kwargs: Additional arguments for APIError
        """
        data = kwargs.pop("data", {})
        if quota_type:
            data["quota_type"] = quota_type
        if reset_time:
            data["reset_time"] = reset_time
        
        headers = kwargs.pop("headers", {})
        if reset_time:
            headers["Retry-After"] = str(reset_time)
            
        super().__init__(
            status_code=429, detail=detail, code=code, data=data, headers=headers, **kwargs
        )


class ModelExecutionError(APIError):
    """Error in ML model execution."""
    
    def __init__(
        self,
        detail: str = "ML model execution error",
        code: str = "model_execution_error",
        model_name: Optional[str] = None,
        error_type: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize model execution error.
        
        Args:
            detail: Error detail message
            code: Error code
            model_name: Name of the ML model
            error_type: Type of model error
            **kwargs: Additional arguments for APIError
        """
        data = kwargs.pop("data", {})
        if model_name:
            data["model_name"] = model_name
        if error_type:
            data["error_type"] = error_type
        super().__init__(
            status_code=500, detail=detail, code=code, data=data, **kwargs
        )


class AdPersonalizationError(AlgorithmError):
    """Error in ad personalization."""
    
    def __init__(
        self,
        detail: str = "Failed to personalize advertisements",
        code: str = "ad_personalization_error",
        ad_type: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize ad personalization error.
        
        Args:
            detail: Error detail message
            code: Error code
            ad_type: Type of advertisement
            **kwargs: Additional arguments for AlgorithmError
        """
        data = kwargs.pop("data", {})
        if ad_type:
            data["ad_type"] = ad_type
        super().__init__(
            detail=detail, code=code, data=data, **kwargs
        )


class PredictionTimeoutError(APIError):
    """Error when ML prediction times out."""
    
    def __init__(
        self,
        detail: str = "ML prediction request timeout",
        code: str = "prediction_timeout",
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        **kwargs,
    ):
        """
        Initialize prediction timeout error.
        
        Args:
            detail: Error detail message
            code: Error code
            model_name: Name of the ML model
            timeout_seconds: Timeout in seconds
            **kwargs: Additional arguments for APIError
        """
        data = kwargs.pop("data", {})
        if model_name:
            data["model_name"] = model_name
        if timeout_seconds:
            data["timeout_seconds"] = timeout_seconds
        super().__init__(
            status_code=504, detail=detail, code=code, data=data, **kwargs
        )
