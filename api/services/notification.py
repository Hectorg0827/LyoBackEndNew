"""
Notification service.

This module provides services for notification operations.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from fastapi import Depends, WebSocket, WebSocketDisconnect
from google.cloud.firestore_v1.base_query import FieldFilter

from api.db.firestore import db
from api.db.redis import redis_client
from api.schemas.notification import Notification, NotificationType, WebSocketEvent

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Notification manager.
    
    This class manages active WebSocket connections and sends
    real-time notifications to connected clients.
    """
    
    def __init__(self):
        """Initialize notification manager."""
        # Map of user_id -> WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        """
        Connect a user's WebSocket.
        
        Args:
            user_id: User ID
            websocket: WebSocket connection
        """
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
            
        self.active_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, user_id: str, websocket: WebSocket):
        """
        Disconnect a user's WebSocket.
        
        Args:
            user_id: User ID
            websocket: WebSocket connection
        """
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_notification(self, user_id: str, event: WebSocketEvent):
        """
        Send notification to a user.
        
        Args:
            user_id: User ID
            event: WebSocket event
        """
        if user_id not in self.active_connections:
            return
            
        connections = self.active_connections[user_id]
        if not connections:
            return
            
        # Message to send
        message = json.dumps(event.model_dump())
        
        # Send to all connections for this user
        for connection in list(connections):
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.disconnect(user_id, connection)
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
                self.disconnect(user_id, connection)
    
    async def broadcast_event(self, user_ids: List[str], event: WebSocketEvent):
        """
        Broadcast event to multiple users.
        
        Args:
            user_ids: List of user IDs
            event: WebSocket event
        """
        tasks = []
        for user_id in user_ids:
            if user_id in self.active_connections:
                tasks.append(self.send_notification(user_id, event))
                
        if tasks:
            await asyncio.gather(*tasks)


# Global notification manager
notification_manager = NotificationManager()


class NotificationService:
    """Notification service."""
    
    async def create_notification(
        self,
        user_id: str,
        type: NotificationType,
        message: str,
        actor_id: Optional[str] = None,
        target_id: Optional[str] = None,
        target_type: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Notification:
        """
        Create a notification.
        
        Args:
            user_id: User ID
            type: Notification type
            message: Notification message
            actor_id: Actor ID (optional)
            target_id: Target ID (optional)
            target_type: Target type (optional)
            image_url: Image URL (optional)
            
        Returns:
            Notification: Created notification
        """
        try:
            # Create notification document
            now = datetime.utcnow()
            
            notification_data = {
                "user_id": user_id,
                "type": type,
                "message": message,
                "actor_id": actor_id,
                "target_id": target_id,
                "target_type": target_type,
                "image_url": image_url,
                "created_at": now,
                "is_read": False,
            }
            
            # Add to Firestore
            notification_ref = await db.collection("notifications").add(notification_data)
            notification_id = notification_ref.id
            
            # Create notification object
            notification = Notification(
                id=notification_id,
                type=type,
                message=message,
                created_at=now,
                is_read=False,
                image_url=image_url,
            )
            
            # If actor_id is provided, get actor details
            if actor_id:
                from api.services.user import UserService
                
                user_service = UserService()
                actor = await user_service.get_by_id(actor_id)
                if actor:
                    notification.actor = {
                        "id": actor.id,
                        "email": actor.email,
                        "display_name": actor.display_name,
                        "avatar_url": actor.avatar_url,
                        "bio": actor.bio,
                        "lang": actor.lang,
                        "followers_count": getattr(actor, "followers_count", 0),
                        "following_count": getattr(actor, "following_count", 0),
                        "created_at": actor.created_at,
                        "updated_at": actor.updated_at,
                        "is_active": actor.is_active,
                        "is_verified": actor.is_verified,
                    }
            
            # Send real-time notification if user is connected
            await self.send_realtime_notification(user_id, notification)
            
            # Publish to Pub/Sub for potential 3rd-party integrations
            # This would be handled by a separate service in production
            
            return notification
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise
    
    async def get_notifications(
        self, user_id: str, limit: int = 20, cursor: Optional[str] = None
    ) -> List[Notification]:
        """
        Get user notifications.
        
        Args:
            user_id: User ID
            limit: Maximum number of notifications to return
            cursor: Pagination cursor
            
        Returns:
            List[Notification]: List of notifications
        """
        try:
            # Query notifications
            query = (
                db.collection("notifications")
                .where("user_id", "==", user_id)
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
            )
            
            # Apply cursor if provided
            if cursor:
                import base64
                
                try:
                    cursor_bytes = base64.b64decode(cursor)
                    timestamp = datetime.fromtimestamp(int(cursor_bytes) / 1000)
                    query = query.start_after({
                        "created_at": timestamp,
                    })
                except Exception as e:
                    logger.warning(f"Invalid cursor: {e}")
            
            # Execute query
            docs = await query.get()
            
            # Get actor IDs
            actor_ids = set()
            for doc in docs:
                actor_id = doc.get("actor_id")
                if actor_id:
                    actor_ids.add(actor_id)
            
            # Get actors
            from api.services.user import UserService
            
            user_service = UserService()
            actors = {}
            for actor_id in actor_ids:
                actor = await user_service.get_by_id(actor_id)
                if actor:
                    actors[actor_id] = actor
            
            # Build notifications
            notifications = []
            for doc in docs:
                data = doc.to_dict()
                
                # Get actor if available
                actor = None
                actor_id = data.get("actor_id")
                if actor_id and actor_id in actors:
                    actor_obj = actors[actor_id]
                    actor = {
                        "id": actor_obj.id,
                        "email": actor_obj.email,
                        "display_name": actor_obj.display_name,
                        "avatar_url": actor_obj.avatar_url,
                        "bio": actor_obj.bio,
                        "lang": actor_obj.lang,
                        "followers_count": getattr(actor_obj, "followers_count", 0),
                        "following_count": getattr(actor_obj, "following_count", 0),
                        "created_at": actor_obj.created_at,
                        "updated_at": actor_obj.updated_at,
                        "is_active": actor_obj.is_active,
                        "is_verified": actor_obj.is_verified,
                    }
                
                # Convert Firestore timestamp
                created_at = data.get("created_at")
                if isinstance(created_at, dict):
                    created_at = datetime.fromtimestamp(created_at["seconds"])
                
                notification = Notification(
                    id=doc.id,
                    type=data.get("type"),
                    actor=actor,
                    target_id=data.get("target_id"),
                    target_type=data.get("target_type"),
                    message=data.get("message"),
                    created_at=created_at or datetime.utcnow(),
                    is_read=data.get("is_read", False),
                    image_url=data.get("image_url"),
                )
                
                notifications.append(notification)
            
            return notifications
        except Exception as e:
            logger.error(f"Error getting notifications: {e}")
            return []
    
    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Mark notification as read.
        
        Args:
            notification_id: Notification ID
            user_id: User ID
            
        Returns:
            bool: True if successful
        """
        try:
            # Get notification
            notification_ref = db.collection("notifications").document(notification_id)
            notification_doc = await notification_ref.get()
            
            if not notification_doc.exists:
                return False
                
            # Check if user owns the notification
            notification_data = notification_doc.to_dict()
            if notification_data.get("user_id") != user_id:
                return False
                
            # Update
            await notification_ref.update({"is_read": True})
            return True
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False
    
    async def mark_all_as_read(self, user_id: str) -> int:
        """
        Mark all notifications as read.
        
        Args:
            user_id: User ID
            
        Returns:
            int: Number of notifications marked as read
        """
        try:
            # Get unread notifications
            query = (
                db.collection("notifications")
                .where("user_id", "==", user_id)
                .where("is_read", "==", False)
            )
            
            docs = await query.get()
            count = len(docs)
            
            # Update in batches
            batch = db.batch()
            for doc in docs:
                ref = db.collection("notifications").document(doc.id)
                batch.update(ref, {"is_read": True})
                
            await batch.commit()
            return count
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return 0
    
    async def get_unread_count(self, user_id: str) -> int:
        """
        Get number of unread notifications.
        
        Args:
            user_id: User ID
            
        Returns:
            int: Number of unread notifications
        """
        try:
            # Try to get from Redis first
            if redis_client:
                count = await redis_client.get(f"unread_count:{user_id}")
                if count is not None:
                    return int(count)
            
            # Get from Firestore
            query = (
                db.collection("notifications")
                .where("user_id", "==", user_id)
                .where("is_read", "==", False)
            )
            
            docs = await query.count().get()
            count = docs[0][0].value
            
            # Cache in Redis
            if redis_client:
                await redis_client.set(f"unread_count:{user_id}", count, ex=300)  # 5 min TTL
                
            return count
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0
    
    async def send_realtime_notification(self, user_id: str, notification: Notification):
        """
        Send real-time notification to user.
        
        Args:
            user_id: User ID
            notification: Notification to send
        """
        try:
            # Create event
            event = WebSocketEvent(
                event_type="notification",
                data=notification.model_dump(),
            )
            
            # Send via WebSocket if user is connected
            await notification_manager.send_notification(user_id, event)
        except Exception as e:
            logger.error(f"Error sending realtime notification: {e}")
    
    async def handle_websocket(self, websocket: WebSocket, user_id: str):
        """
        Handle WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            user_id: User ID
        """
        try:
            # Connect
            await notification_manager.connect(user_id, websocket)
            
            # Send initial unread count
            unread_count = await self.get_unread_count(user_id)
            
            await websocket.send_json({
                "event_type": "unread_count",
                "data": {"count": unread_count},
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            # Wait for messages (ping/pong)
            while True:
                message = await websocket.receive_text()
                
                # Handle ping
                if message == "ping":
                    await websocket.send_text("pong")
                    
                # Other message types could be handled here
                
        except WebSocketDisconnect:
            notification_manager.disconnect(user_id, websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            notification_manager.disconnect(user_id, websocket)
