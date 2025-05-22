"""
Content Retrieval module for external educational content.

This module provides services that retrieve and process content
from external APIs such as YouTube, Google Books, etc.
"""
import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, TypeVar, Generic

import httpx

from api.core.ai_config import ai_config
from api.core.content_moderation import content_moderator
from api.core.resource_manager import ai_resource_manager
from api.core.tiered_computation import cached_result, with_tiered_computation
from api.core.error_utils_ai import graceful_ai_degradation
from api.schemas.content import (
    ContentType,
    ExternalBook,
    ExternalCourse,
    ExternalPodcast,
    ExternalVideo,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ContentSource(str, Enum):
    """External content sources."""
    
    YOUTUBE = "youtube"
    GOOGLE_BOOKS = "google_books"
    UDEMY = "udemy"
    COURSERA = "coursera"
    KHAN_ACADEMY = "khan_academy"
    SPOTIFY = "spotify"
    APPLE_PODCASTS = "apple_podcasts"
    CUSTOM_API = "custom_api"


class ContentRelevance(Enum):
    """Content relevance levels."""
    
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    UNRELATED = 0


class ContentMetadata(Generic[T]):
    """Metadata for retrieved content."""
    
    def __init__(
        self,
        content: T,
        source: ContentSource,
        relevance: ContentRelevance = ContentRelevance.MEDIUM,
        last_updated: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize content metadata.
        
        Args:
            content: The content object
            source: Source of the content
            relevance: Relevance score
            last_updated: Last update timestamp
            metadata: Additional metadata
        """
        self.content = content
        self.source = source
        self.relevance = relevance
        self.last_updated = last_updated or time.time()
        self.metadata = metadata or {}
        

class ContentRetrievalService:
    """Service for retrieving external educational content."""
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        Initialize the content retrieval service.
        
        Args:
            api_keys: API keys for various services
        """
        self.api_keys = api_keys or {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
    async def __del__(self):
        """Clean up resources."""
        await self.http_client.aclose()
        
    async def search_all_sources(
        self,
        query: str,
        content_filters: Optional[Dict[str, Any]] = None,
        max_results: int = 5,
        safe_search: bool = True
    ) -> Dict[str, List[Any]]:
        """
        Search all supported content sources.
        
        Args:
            query: Search query
            content_filters: Filters to apply to the results
            max_results: Maximum number of results per source
            safe_search: Whether to enable safe search filters
            
        Returns:
            Dictionary of content lists by type
        """
        # Run searches in parallel
        videos_task = self.search_videos(query, max_results=max_results, safe_search=safe_search)
        books_task = self.search_books(query, max_results=max_results)
        courses_task = self.search_courses(query, max_results=max_results)
        podcasts_task = self.search_podcasts(query, max_results=max_results)
        
        videos, books, courses, podcasts = await asyncio.gather(
            videos_task, books_task, courses_task, podcasts_task
        )
        
        # Apply content filters if provided
        if content_filters:
            videos = self._apply_filters(videos, content_filters.get("videos", {}))
            books = self._apply_filters(books, content_filters.get("books", {}))
            courses = self._apply_filters(courses, content_filters.get("courses", {}))
            podcasts = self._apply_filters(podcasts, content_filters.get("podcasts", {}))
            
        return {
            "videos": videos,
            "books": books,
            "courses": courses,
            "podcasts": podcasts,
        }
    
    def _apply_filters(self, items: List[T], filters: Dict[str, Any]) -> List[T]:
        """
        Apply filters to a list of items.
        
        Args:
            items: List of content items
            filters: Filters to apply
            
        Returns:
            Filtered list of items
        """
        if not filters:
            return items
            
        filtered_items = items.copy()
        
        # Apply each filter
        for key, value in filters.items():
            if value is None:
                continue
                
            if key == "min_date":
                filtered_items = [
                    item for item in filtered_items 
                    if getattr(item, "published_at", datetime.now()) >= value
                ]
            elif key == "max_date":
                filtered_items = [
                    item for item in filtered_items 
                    if getattr(item, "published_at", datetime.now()) <= value
                ]
            elif key == "language":
                filtered_items = [
                    item for item in filtered_items 
                    if getattr(item, "language", "en") == value
                ]
            # Add more filters as needed
                
        return filtered_items
    
    @cached_result(ttl_key="content_retrieval")
    @graceful_ai_degradation(fallback_value=[])
    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        safe_search: bool = True
    ) -> List[ExternalVideo]:
        """
        Search for educational videos.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            safe_search: Whether to enable safe search
            
        Returns:
            List of video results
        """
        try:
            youtube_key = self.api_keys.get("youtube")
            if not youtube_key:
                logger.error("No YouTube API key available")
                return []
                
            # Build the YouTube search request
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "q": f"{query} education tutorial",
                "maxResults": max_results * 2,  # Request more to filter later
                "part": "snippet",
                "type": "video",
                "videoCategoryId": "27",  # Education category
                "relevanceLanguage": "en",
                "key": youtube_key,
            }
            
            if safe_search:
                params["safeSearch"] = "strict"
                
            # Make the request
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Process search results
            video_ids = []
            snippet_map = {}
            for item in data.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if video_id:
                    video_ids.append(video_id)
                    snippet_map[video_id] = item.get("snippet", {})
            
            # If no videos found, return empty list
            if not video_ids:
                return []
                
            # Get video details
            details_url = "https://www.googleapis.com/youtube/v3/videos"
            details_params = {
                "id": ",".join(video_ids),
                "part": "snippet,contentDetails,statistics",
                "key": youtube_key,
            }
            
            details_response = await self.http_client.get(details_url, params=details_params)
            details_data = details_response.json()
            
            # Process video details
            videos = []
            for item in details_data.get("items", []):
                video_id = item.get("id")
                snippet = snippet_map.get(video_id, {})
                content_details = item.get("contentDetails", {})
                statistics = item.get("statistics", {})
                
                # Parse ISO 8601 duration (simplified)
                duration_str = content_details.get("duration", "PT0M0S")
                
                # Extract hours, minutes, seconds
                hours = re.search(r'(\d+)H', duration_str)
                minutes = re.search(r'(\d+)M', duration_str)
                seconds = re.search(r'(\d+)S', duration_str)
                
                # Calculate total seconds
                total_seconds = 0
                if hours:
                    total_seconds += int(hours.group(1)) * 3600
                if minutes:
                    total_seconds += int(minutes.group(1)) * 60
                if seconds:
                    total_seconds += int(seconds.group(1))
                
                # Convert published time to datetime
                published_at = None
                if snippet.get("publishedAt"):
                    published_at = datetime.fromisoformat(
                        snippet.get("publishedAt").replace("Z", "+00:00")
                    )
                
                # Create video object
                video = ExternalVideo(
                    id=video_id,
                    title=snippet.get("title", "Unknown Title"),
                    channel=snippet.get("channelTitle", "Unknown Channel"),
                    channel_id=snippet.get("channelId", ""),
                    description=snippet.get("description", ""),
                    published_at=published_at or datetime.now(),
                    duration=total_seconds,
                    thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    video_url=f"https://www.youtube.com/watch?v={video_id}",
                    view_count=int(statistics.get("viewCount", 0)) if "viewCount" in statistics else None,
                    language=snippet.get("defaultLanguage", "en"),
                )
                videos.append(video)
                
                # Only return the requested number of videos
                if len(videos) >= max_results:
                    break
            
            return videos
            
        except Exception as e:
            logger.error(f"Error searching videos: {str(e)}")
            return []
    
    @cached_result(ttl_key="content_retrieval")
    @graceful_ai_degradation(fallback_value=[])
    async def search_books(
        self,
        query: str,
        max_results: int = 5
    ) -> List[ExternalBook]:
        """
        Search for educational books.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of book results
        """
        try:
            google_books_key = self.api_keys.get("google_books")
            if not google_books_key:
                logger.error("No Google Books API key available")
                return []
                
            # Build the Google Books search request
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {
                "q": f"{query}+subject:education",
                "maxResults": max_results,
                "printType": "books",
                "key": google_books_key,
            }
            
            # Make the request
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Process search results
            books = []
            for item in data.get("items", []):
                volume_info = item.get("volumeInfo", {})
                
                # Try to parse published date
                published_date = None
                if volume_info.get("publishedDate"):
                    try:
                        # Handle different date formats
                        date_str = volume_info.get("publishedDate")
                        if len(date_str) == 4:  # Year only
                            published_date = date_str
                        else:
                            # Try to parse as full date
                            published_date = datetime.strptime(
                                date_str, "%Y-%m-%d"
                            ).strftime("%Y-%m-%d")
                    except ValueError:
                        published_date = volume_info.get("publishedDate")
                
                # Create book object
                book = ExternalBook(
                    id=item.get("id"),
                    title=volume_info.get("title", "Unknown Title"),
                    authors=volume_info.get("authors", []),
                    publisher=volume_info.get("publisher"),
                    published_date=published_date,
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
            logger.error(f"Error searching books: {str(e)}")
            return []
    
    @cached_result(ttl_key="content_retrieval")
    @graceful_ai_degradation(fallback_value=[])
    async def search_courses(
        self,
        query: str,
        max_results: int = 5
    ) -> List[ExternalCourse]:
        """
        Search for educational courses.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of course results
        """
        try:
            # In a real implementation, this would call Udemy, Coursera, etc. APIs
            # For this example, we'll just return mock data
            
            # Use AI to generate relevant course titles and descriptions
            async with ai_resource_manager.managed_resource(
                "model", "content_generator"
            ) as model:
                course_data = await model.generate_content(
                    content_type="courses",
                    query=query,
                    count=max_results
                )
            
            courses = []
            for i, data in enumerate(course_data):
                course_id = f"course-{uuid.uuid4()}"
                
                # Create a random publication date within the last 2 years
                days_ago = (i * 30) % 730  # Stagger dates
                published_date = datetime.now() - timedelta(days=days_ago)
                
                # Create course object
                course = ExternalCourse(
                    id=course_id,
                    title=data.get("title", f"{query} Course {i+1}"),
                    provider=data.get("provider", "Learning Platform"),
                    instructor=data.get("instructor", "Expert Instructor"),
                    description=data.get("description", f"A course about {query}"),
                    url=data.get("url", f"https://example.com/courses/{course_id}"),
                    image_url=data.get("image_url", f"https://example.com/courses/{course_id}.jpg"),
                    level=data.get("level", "Intermediate"),
                    topics=data.get("topics", [query, "Education"]),
                    duration=data.get("duration", 1200),  # Default to 20 hours
                    language=data.get("language", "en"),
                )
                courses.append(course)
            
            return courses
            
        except Exception as e:
            logger.error(f"Error searching courses: {str(e)}")
            return []
    
    @cached_result(ttl_key="content_retrieval")
    @graceful_ai_degradation(fallback_value=[])
    async def search_podcasts(
        self,
        query: str,
        max_results: int = 5
    ) -> List[ExternalPodcast]:
        """
        Search for educational podcasts.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of podcast results
        """
        try:
            # In a real implementation, this would call Spotify, Apple Podcasts, etc. APIs
            # For this example, we'll just return mock data
            
            # Use AI to generate relevant podcast titles and descriptions
            async with ai_resource_manager.managed_resource(
                "model", "content_generator"
            ) as model:
                podcast_data = await model.generate_content(
                    content_type="podcasts",
                    query=query,
                    count=max_results
                )
            
            podcasts = []
            for i, data in enumerate(podcast_data):
                podcast_id = f"podcast-{uuid.uuid4()}"
                
                # Create a random publication date within the last 2 months
                days_ago = (i * 7) % 60  # Stagger dates
                published_date = datetime.now() - timedelta(days=days_ago)
                
                # Create podcast object
                podcast = ExternalPodcast(
                    id=podcast_id,
                    title=data.get("title", f"{query} Podcast {i+1}"),
                    author=data.get("author", "Podcast Network"),
                    description=data.get("description", f"A podcast about {query}"),
                    published_at=published_date,
                    duration=data.get("duration", 1800),  # Default to 30 minutes
                    image_url=data.get("image_url", f"https://example.com/podcasts/{podcast_id}.jpg"),
                    audio_url=data.get("audio_url", f"https://example.com/podcasts/{podcast_id}.mp3"),
                    rss_url=data.get("rss_url", "https://example.com/podcasts/feed.xml"),
                    language=data.get("language", "en"),
                )
                podcasts.append(podcast)
            
            return podcasts
            
        except Exception as e:
            logger.error(f"Error searching podcasts: {str(e)}")
            return []
    
    async def evaluate_content_relevance(
        self,
        content: Union[ExternalBook, ExternalVideo, ExternalPodcast, ExternalCourse],
        query: str
    ) -> ContentRelevance:
        """
        Evaluate the relevance of content to a query.
        
        Args:
            content: The content to evaluate
            query: The original search query
            
        Returns:
            ContentRelevance score
        """
        try:
            # In a production environment, you'd likely use embeddings for this
            # For now, we'll use a simple text-based approach
            
            # Extract searchable text
            text = ""
            if hasattr(content, "title"):
                text += content.title + " "
            if hasattr(content, "description") and content.description:
                text += content.description + " "
                
            # For books, include authors and categories
            if isinstance(content, ExternalBook):
                if content.authors:
                    text += " ".join(content.authors) + " "
                if content.categories:
                    text += " ".join(content.categories) + " "
                    
            # For videos, include channel info
            if isinstance(content, ExternalVideo):
                text += content.channel + " "
                
            # For courses, include topics
            if isinstance(content, ExternalCourse):
                if content.topics:
                    text += " ".join(content.topics) + " "
            
            # Normalize to lower case
            text = text.lower()
            query = query.lower()
            
            # Check for exact match
            if query in text:
                return ContentRelevance.HIGH
                
            # Check for partial matches
            query_terms = query.split()
            matches = sum(1 for term in query_terms if term in text)
            match_ratio = matches / len(query_terms)
            
            if match_ratio >= 0.8:
                return ContentRelevance.HIGH
            elif match_ratio >= 0.5:
                return ContentRelevance.MEDIUM
            elif match_ratio > 0:
                return ContentRelevance.LOW
                
            return ContentRelevance.UNRELATED
            
        except Exception as e:
            logger.error(f"Error evaluating content relevance: {str(e)}")
            return ContentRelevance.MEDIUM  # Default to medium relevance
    
    async def filter_for_educational_value(
        self,
        content_items: List[Union[ExternalBook, ExternalVideo, ExternalPodcast, ExternalCourse]],
        min_relevance: ContentRelevance = ContentRelevance.MEDIUM
    ) -> List[Union[ExternalBook, ExternalVideo, ExternalPodcast, ExternalCourse]]:
        """
        Filter content items for educational value.
        
        Args:
            content_items: List of content items
            min_relevance: Minimum relevance score
            
        Returns:
            Filtered content items
        """
        # In a real implementation, this would use the AI to analyze content
        # For this example, we'll just return the input list
        return content_items


# Create a singleton instance
content_retrieval_service = ContentRetrievalService()
