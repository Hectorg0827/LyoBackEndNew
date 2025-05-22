"""
Firestore helpers for Avatar context and conversation persistence.
"""
import logging
from typing import Dict, Any
from api.db.firestore import db

AVATAR_COLLECTION = "avatar_contexts"

logger = logging.getLogger(__name__)

async def save_avatar_context(user_id: str, context_data: Dict[str, Any]) -> None:
    """Save avatar context and conversation to Firestore."""
    if not db:
        logger.error("Firestore client not initialized")
        return
    try:
        await db.collection(AVATAR_COLLECTION).document(user_id).set(context_data)
    except Exception as e:
        logger.error(f"Failed to save avatar context for {user_id}: {e}")

async def load_avatar_context(user_id: str) -> Dict[str, Any]:
    """Load avatar context and conversation from Firestore."""
    if not db:
        logger.error("Firestore client not initialized")
        return {}
    try:
        doc = await db.collection(AVATAR_COLLECTION).document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return {}
    except Exception as e:
        logger.error(f"Failed to load avatar context for {user_id}: {e}")
        return {}
