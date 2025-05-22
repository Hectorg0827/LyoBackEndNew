"""
Base schemas for Lyo API.

This module defines base schemas for request and response models.
"""
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

# Type variable for generic models
T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema model."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        json_encoders={datetime: lambda dt: dt.isoformat()},
    )


class PaginatedResponse(BaseSchema, Generic[T]):
    """Paginated response model."""
    
    items: List[T]
    total: int
    page: int = 1
    size: int
    pages: int
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None


class SuccessResponse(BaseSchema):
    """Success response model."""
    
    success: bool = True
    message: str


class ErrorResponse(BaseSchema):
    """Error response model."""
    
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
