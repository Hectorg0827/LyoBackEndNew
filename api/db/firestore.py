"""
Firestore database module.

This module handles Firestore database initialization and provides
helper functions for database operations.
"""
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import AsyncClient, DocumentReference, DocumentSnapshot
from google.cloud.firestore_v1.base_query import BaseQuery

from api.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
try:
    if settings.FIRESTORE_EMULATOR_HOST:
        # Use emulator for local development
        firebase_app = firebase_admin.initialize_app(
            options={"projectId": settings.FIRESTORE_PROJECT_ID or "lyo-dev"}
        )
    else:
        # Use service account for production
        cred = credentials.ApplicationDefault()
        firebase_app = firebase_admin.initialize_app(
            cred, {"projectId": settings.FIRESTORE_PROJECT_ID}
        )
        
    # Create Firestore client
    db = firestore.AsyncClient(project=settings.FIRESTORE_PROJECT_ID)
    logger.info("Firestore client initialized")
except Exception as e:
    logger.exception(f"Failed to initialize Firestore: {e}")
    # Create a placeholder that will raise exceptions when used
    db = None

# Type for Firestore model classes
T = TypeVar("T")


class FirestoreModel:
    """Base class for Firestore models."""
    
    collection_name: str
    
    @classmethod
    async def get_by_id(cls: Type[T], doc_id: str) -> Optional[T]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Optional[T]: The document as a model instance, or None if not found
        """
        if not db:
            raise RuntimeError("Firestore client not initialized")
            
        doc_ref = db.collection(cls.collection_name).document(doc_id)
        doc = await doc_ref.get()
        
        if not doc.exists:
            return None
            
        return cls.from_dict(doc.to_dict(), doc_id)
    
    @classmethod
    async def get_by_field(
        cls: Type[T], field: str, value: Any, limit: int = 1
    ) -> List[T]:
        """
        Get documents by field value.
        
        Args:
            field: Field name
            value: Field value
            limit: Maximum number of documents to return
            
        Returns:
            List[T]: List of model instances
        """
        if not db:
            raise RuntimeError("Firestore client not initialized")
            
        query = db.collection(cls.collection_name).where(field, "==", value).limit(limit)
        docs = await query.get()
        
        return [cls.from_dict(doc.to_dict(), doc.id) for doc in docs]
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any], doc_id: str) -> T:
        """
        Create a model instance from a dictionary.
        
        Args:
            data: Dictionary containing document data
            doc_id: Document ID
            
        Returns:
            T: Model instance
        """
        # Implementation depends on specific model
        raise NotImplementedError()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the model
        """
        # Implementation depends on specific model
        raise NotImplementedError()
    
    async def save(self) -> str:
        """
        Save the model to Firestore.
        
        Returns:
            str: Document ID
        """
        if not db:
            raise RuntimeError("Firestore client not initialized")
            
        data = self.to_dict()
        
        # If the model has an id, update existing document
        if hasattr(self, "id") and getattr(self, "id"):
            doc_ref = db.collection(self.collection_name).document(getattr(self, "id"))
            await doc_ref.set(data)
            return getattr(self, "id")
            
        # Otherwise create a new document
        doc_ref = await db.collection(self.collection_name).add(data)
        return doc_ref.id
    
    @classmethod
    async def delete(cls, doc_id: str) -> None:
        """
        Delete a document by ID.
        
        Args:
            doc_id: Document ID
        """
        if not db:
            raise RuntimeError("Firestore client not initialized")
            
        await db.collection(cls.collection_name).document(doc_id).delete()
