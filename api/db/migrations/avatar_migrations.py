"""
Migration tools for Avatar context version changes.
"""
import asyncio
import logging
from typing import Dict, Any, List
from api.db.firestore import db
from api.core.avatar import AvatarContext, AvatarMessage

logger = logging.getLogger(__name__)

BATCH_SIZE = 100

async def migrate_avatar_contexts(version_from: str, version_to: str) -> Dict[str, Any]:
    """
    Migrate all avatar contexts from one version to another.
    
    Args:
        version_from: Current version
        version_to: Target version
        
    Returns:
        Migration statistics
    """
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0
    }
    
    try:
        # Get all contexts
        docs = db.collection("avatar_contexts").stream()
        
        async for doc in docs:
            stats["total"] += 1
            try:
                data = doc.to_dict()
                
                # Skip if already at target version
                if data.get("version") == version_to:
                    stats["skipped"] += 1
                    continue
                
                # Apply version-specific migrations
                migrated_data = await migrate_context_data(data, version_from, version_to)
                
                # Update in Firestore
                await db.collection("avatar_contexts").document(doc.id).set(migrated_data)
                stats["success"] += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate context {doc.id}: {e}")
                stats["failed"] += 1
                
            # Log progress periodically
            if (stats["total"] % 100) == 0:
                logger.info(f"Migration progress: {stats}")
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        
    return stats

async def migrate_context_data(data: Dict[str, Any], version_from: str, version_to: str) -> Dict[str, Any]:
    """
    Migrate a single context's data between versions.
    
    Args:
        data: Context data to migrate
        version_from: Current version
        version_to: Target version
        
    Returns:
        Migrated context data
    """
    # Handle specific version migrations
    if version_from == "1.0" and version_to == "1.1":
        return migrate_1_0_to_1_1(data)
    elif version_from == "1.1" and version_to == "1.2":
        return migrate_1_1_to_1_2(data)
    else:
        raise ValueError(f"Unsupported version migration: {version_from} -> {version_to}")

def migrate_1_0_to_1_1(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate from version 1.0 to 1.1 (add learning style and pace)."""
    context = data.get("context", {})
    
    # Add new fields with default values
    if "learning_style" not in context:
        context["learning_style"] = None
    if "learning_pace" not in context:
        context["learning_pace"] = None
        
    data["context"] = context
    data["version"] = "1.1"
    
    return data

def migrate_1_1_to_1_2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate from version 1.1 to 1.2 (add interaction patterns)."""
    context = data.get("context", {})
    
    # Add new interaction patterns if not present
    if "interaction_patterns" not in context:
        context["interaction_patterns"] = {
            "avg_response_time": 0,
            "avg_message_length": 0,
            "session_count": 0,
            "total_interactions": len(data.get("conversation", []))
        }
        
    data["context"] = context
    data["version"] = "1.2"
    
    return data

async def rollback_migration(version_from: str, cutoff_time: float) -> Dict[str, Any]:
    """
    Rollback a migration for contexts updated after a certain time.
    
    Args:
        version_from: Version to rollback to
        cutoff_time: Unix timestamp to rollback changes after
        
    Returns:
        Rollback statistics
    """
    stats = {
        "total": 0,
        "rolled_back": 0,
        "failed": 0
    }
    
    try:
        # Get contexts updated after cutoff
        docs = (db.collection("avatar_contexts")
               .where("timestamp", ">=", cutoff_time)
               .stream())
        
        async for doc in docs:
            stats["total"] += 1
            try:
                data = doc.to_dict()
                
                # Restore backup if exists
                backup_doc = await db.collection("avatar_contexts_backup").document(doc.id).get()
                if backup_doc.exists:
                    backup_data = backup_doc.to_dict()
                    if backup_data.get("version") == version_from:
                        await db.collection("avatar_contexts").document(doc.id).set(backup_data)
                        stats["rolled_back"] += 1
                        
            except Exception as e:
                logger.error(f"Failed to rollback context {doc.id}: {e}")
                stats["failed"] += 1
                
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        
    return stats
