"""
Content service.

This module provides services for content operations.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
from fastapi import Depends, HTTPException, status
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google.cloud.storage import Client as StorageClient

from api.core.config import settings
from api.db.redis import cache
from api.schemas.content import (
    ContentType,
    ExternalBook,
    ExternalCourse,
    ExternalPodcast,
    ExternalVideo,
    UploadCompleteRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)

logger = logging.getLogger(__name__)


class ContentService:
    """Content service."""
    
    def __init__(self):
        """Initialize content service."""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Initialize storage client
        try:
            self.storage_client = StorageClient(project=settings.FIRESTORE_PROJECT_ID)
            self.bucket = self.storage_client.bucket(settings.STORAGE_BUCKET_NAME)
        except Exception as e:
            logger.error(f"Failed to initialize storage client: {e}")
            self.storage_client = None
            self.bucket = None
    
    async def __del__(self):
        """Cleanup resources."""
        await self.http_client.aclose()
    
    async def generate_upload_url(
        self, user_id: str, request: UploadUrlRequest
    ) -> UploadUrlResponse:
        """
        Generate signed URL for upload.
        
        Args:
            user_id: User ID
            request: Upload URL request
            
        Returns:
            UploadUrlResponse: Upload URL response
            
        Raises:
            HTTPException: On error
        """
        if not self.storage_client or not self.bucket:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage client not initialized",
            )
        
        try:
            # Generate UUID for resource
            resource_id = str(uuid.uuid4())
            
            # Determine file extension from mime type
            extension = ""
            if request.mime_type == "image/jpeg":
                extension = ".jpg"
            elif request.mime_type == "image/png":
                extension = ".png"
            elif request.mime_type == "image/gif":
                extension = ".gif"
            elif request.mime_type == "video/mp4":
                extension = ".mp4"
            elif request.mime_type == "audio/mpeg":
                extension = ".mp3"
            elif request.mime_type == "application/pdf":
                extension = ".pdf"
            
            # Generate object name
            object_name = f"{user_id}/{request.content_type.value}/{resource_id}{extension}"
            
            # Get blob
            blob = self.bucket.blob(object_name)
            
            # Generate signed URL
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15),
                method="PUT",
                content_type=request.mime_type,
            )
            
            return UploadUrlResponse(
                signed_url=signed_url,
                resource_id=resource_id,
                expires_at=expires_at,
            )
        except Exception as e:
            logger.error(f"Error generating upload URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate upload URL: {str(e)}",
            )
    
    async def complete_upload(
        self, user_id: str, request: UploadCompleteRequest
    ) -> Dict[str, str]:
        """
        Complete upload process.
        
        Args:
            user_id: User ID
            request: Upload complete request
            
        Returns:
            Dict[str, str]: Success response
            
        Raises:
            HTTPException: On error
        """
        if not self.storage_client or not self.bucket:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage client not initialized",
            )
        
        try:
            # Find the blob by resource ID
            prefix = f"{user_id}/"
            for blob in self.bucket.list_blobs(prefix=prefix):
                if request.resource_id in blob.name:
                    # Update metadata
                    blob.metadata = {
                        "user_id": user_id,
                        "resource_id": request.resource_id,
                        "upload_completed_at": datetime.utcnow().isoformat(),
                    }
                    blob.patch()
                    
                    # In a real implementation, we would trigger a Cloud Function
                    # to generate thumbnails, extract metadata, etc.
                    
                    # Get public URL
                    public_url = f"https://storage.googleapis.com/{settings.STORAGE_BUCKET_NAME}/{blob.name}"
                    
                    return {
                        "status": "success",
                        "resource_id": request.resource_id,
                        "public_url": public_url,
                    }
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resource {request.resource_id} not found",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error completing upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to complete upload: {str(e)}",
            )
    
    @cache(prefix="books", ttl=60*60*24)  # Cache for 24 hours
    async def search_books(self, query: str) -> List[ExternalBook]:
        """
        Search for books.
        
        Args:
            query: Search query
            
        Returns:
            List[ExternalBook]: List of books
        """
        try:
            # Use Google Books API
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {
                "q": query,
                "maxResults": 10,
                "printType": "books",
                "key": settings.GOOGLE_BOOKS_API_KEY,
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                books = []
                for item in data.get("items", []):
                    volume_info = item.get("volumeInfo", {})
                    
                    book = ExternalBook(
                        id=item.get("id"),
                        title=volume_info.get("title", "Unknown Title"),
                        authors=volume_info.get("authors", []),
                        publisher=volume_info.get("publisher"),
                        published_date=volume_info.get("publishedDate"),
                        description=volume_info.get("description"),
                        page_count=volume_info.get("pageCount"),
                        categories=volume_info.get("categories", []),
                        image_url=volume_info.get("imageLinks", {}).get("thumbnail"),
                        info_link=volume_info.get("infoLink"),
                        preview_link=volume_info.get("previewLink"),
                        language=volume_info.get("language", "en"),
                    )
                    books.append(book)
                
                return books
        except Exception as e:
            logger.error(f"Error searching books: {e}")
            return []
    
    @cache(prefix="videos", ttl=60*60*24)  # Cache for 24 hours
    async def search_videos(self, query: str) -> List[ExternalVideo]:
        """
        Search for educational videos.
        
        Args:
            query: Search query
            
        Returns:
            List[ExternalVideo]: List of videos
        """
        try:
            # Use YouTube API
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "q": f"{query} education tutorial",
                "maxResults": 10,
                "part": "snippet",
                "type": "video",
                "videoCategoryId": "27",  # Education category
                "key": settings.YOUTUBE_API_KEY,
            }
            
            videos = []
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                for item in data.get("items", []):
                    snippet = item.get("snippet", {})
                    video_id = item.get("id", {}).get("videoId")
                    
                    if not video_id:
                        continue
                    
                    # Get video details
                    details_url = "https://www.googleapis.com/youtube/v3/videos"
                    details_params = {
                        "id": video_id,
                        "part": "snippet,contentDetails,statistics",
                        "key": settings.YOUTUBE_API_KEY,
                    }
                    
                    details_response = await client.get(details_url, params=details_params)
                    details_data = details_response.json()
                    
                    if not details_data.get("items"):
                        continue
                    
                    details = details_data["items"][0]
                    content_details = details.get("contentDetails", {})
                    statistics = details.get("statistics", {})
                    
                    # Parse ISO 8601 duration (simplified)
                    duration_str = content_details.get("duration", "PT0M0S")
                    
                    # Convert published time to datetime
                    published_at = datetime.fromisoformat(
                        snippet.get("publishedAt").replace("Z", "+00:00")
                    )
                    
                    video = ExternalVideo(
                        id=video_id,
                        title=snippet.get("title", "Unknown Title"),
                        channel=snippet.get("channelTitle", "Unknown Channel"),
                        channel_id=snippet.get("channelId", ""),
                        description=snippet.get("description", ""),
                        published_at=published_at,
                        duration=duration_str,
                        thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                        video_url=f"https://www.youtube.com/watch?v={video_id}",
                        view_count=int(statistics.get("viewCount", 0)) if "viewCount" in statistics else None,
                        language=snippet.get("defaultLanguage", "en"),
                    )
                    videos.append(video)
                
                return videos
        except Exception as e:
            logger.error(f"Error searching videos: {e}")
            return []
    
    @cache(prefix="podcasts", ttl=60*60*24)  # Cache for 24 hours
    async def search_podcasts(self, query: str) -> List[ExternalPodcast]:
        """
        Search for educational podcasts.
        
        Args:
            query: Search query
            
        Returns:
            List[ExternalPodcast]: List of podcasts
        """
        try:
            # In a real implementation, this would use a podcast API
            # For now, return some mock data
            podcasts = [
                ExternalPodcast(
                    id=f"podcast-{uuid.uuid4()}",
                    title=f"Learning About {query}",
                    author="Educational Podcasts Network",
                    description=f"A podcast discussing {query} in depth",
                    published_at=datetime.utcnow() - timedelta(days=5),
                    duration=1800,  # 30 minutes
                    image_url=f"https://example.com/podcasts/{query.replace(' ', '-')}.jpg",
                    audio_url=f"https://example.com/podcasts/{query.replace(' ', '-')}.mp3",
                    rss_url="https://example.com/podcasts/feed.xml",
                    language="en",
                ),
                ExternalPodcast(
                    id=f"podcast-{uuid.uuid4()}",
                    title=f"{query} for Beginners",
                    author="Learning Channel",
                    description=f"An introduction to {query} for beginners",
                    published_at=datetime.utcnow() - timedelta(days=10),
                    duration=2400,  # 40 minutes
                    image_url=f"https://example.com/podcasts/beginners-{query.replace(' ', '-')}.jpg",
                    audio_url=f"https://example.com/podcasts/beginners-{query.replace(' ', '-')}.mp3",
                    rss_url="https://example.com/learning/feed.xml",
                    language="en",
                ),
            ]
            
            return podcasts
        except Exception as e:
            logger.error(f"Error searching podcasts: {e}")
            return []
    
    @cache(prefix="courses", ttl=60*60*24)  # Cache for 24 hours
    async def search_courses(self, query: str) -> List[ExternalCourse]:
        """
        Search for online courses.
        
        Args:
            query: Search query
            
        Returns:
            List[ExternalCourse]: List of courses
        """
        try:
            # In a real implementation, this would use APIs from Coursera, edX, etc.
            # For now, return some mock data
            courses = [
                ExternalCourse(
                    id=f"course-{uuid.uuid4()}",
                    title=f"Complete Guide to {query}",
                    provider="OpenCourseWare",
                    instructor="Prof. Jane Smith",
                    description=f"A comprehensive course on {query}",
                    url=f"https://example.com/courses/complete-{query.replace(' ', '-')}",
                    image_url=f"https://example.com/courses/complete-{query.replace(' ', '-')}.jpg",
                    level="Intermediate",
                    topics=[query, "Education", "Learning"],
                    duration=1200,  # 20 hours
                    language="en",
                ),
                ExternalCourse(
                    id=f"course-{uuid.uuid4()}",
                    title=f"Advanced {query} Techniques",
                    provider="Educational Resources",
                    instructor="Dr. John Doe",
                    description=f"An advanced course covering {query} techniques",
                    url=f"https://example.com/courses/advanced-{query.replace(' ', '-')}",
                    image_url=f"https://example.com/courses/advanced-{query.replace(' ', '-')}.jpg",
                    level="Advanced",
                    topics=[query, "Advanced Techniques", "Mastery"],
                    duration=900,  # 15 hours
                    language="en",
                ),
            ]
            
            return courses
        except Exception as e:
            logger.error(f"Error searching courses: {e}")
            return []
