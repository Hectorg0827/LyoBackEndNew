"""
Notifications router.

This module defines the notifications endpoints.
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, WebSocket, status

from api.core.security import get_current_user
from api.models.user import User
from api.schemas.notification import Notification, NotificationResponse
from api.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationResponse)
async def get_notifications(
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = None,
    current_user: Annotated[User, Depends(get_current_user)],
    notification_service: Annotated[NotificationService, Depends()],
):
    """
    Get user notifications.
    
    Args:
        limit: Maximum number of notifications to return
        cursor: Pagination cursor
        current_user: Current authenticated user
        notification_service: Notification service
        
    Returns:
        NotificationResponse: Notifications response
    """
    # Get notifications
    notifications = await notification_service.get_notifications(
        current_user.id, limit, cursor
    )
    
    # Get unread count
    unread_count = await notification_service.get_unread_count(current_user.id)
    
    # Create next cursor
    next_cursor = None
    if notifications and len(notifications) == limit:
        import base64
        
        last_ts = int(notifications[-1].created_at.timestamp() * 1000)
        next_cursor = base64.b64encode(str(last_ts).encode()).decode()
    
    return NotificationResponse(
        items=notifications,
        unread_count=unread_count,
        next_cursor=next_cursor,
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_as_read(
    notification_id: str = Path(..., title="The ID of the notification to mark as read"),
    current_user: Annotated[User, Depends(get_current_user)],
    notification_service: Annotated[NotificationService, Depends()],
):
    """
    Mark notification as read.
    
    Args:
        notification_id: Notification ID
        current_user: Current authenticated user
        notification_service: Notification service
    """
    success = await notification_service.mark_as_read(notification_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_as_read(
    current_user: Annotated[User, Depends(get_current_user)],
    notification_service: Annotated[NotificationService, Depends()],
):
    """
    Mark all notifications as read.
    
    Args:
        current_user: Current authenticated user
        notification_service: Notification service
    """
    await notification_service.mark_all_as_read(current_user.id)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    notification_service: NotificationService = Depends(),
):
    """
    WebSocket endpoint for real-time notifications.
    
    Args:
        websocket: WebSocket connection
        token: Authentication token
        notification_service: Notification service
    """
    try:
        # Validate token
        from jose import JWTError, jwt
        from pydantic import ValidationError

        from api.core.config import settings
        from api.schemas.auth import TokenPayload
        from api.services.user import UserService
        
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            token_data = TokenPayload(**payload)
            
            if token_data.sub is None:
                await websocket.close(code=1008)  # Policy violation
                return
                
        except (JWTError, ValidationError):
            await websocket.close(code=1008)  # Policy violation
            return
        
        # Get user
        user_service = UserService()
        user = await user_service.get_by_id(token_data.sub)
        if user is None:
            await websocket.close(code=1008)  # Policy violation
            return
            
        # Handle WebSocket connection
        await notification_service.handle_websocket(websocket, user.id)
    except Exception as e:
        import logging
        
        logging.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)  # Internal error
        except:
            pass
