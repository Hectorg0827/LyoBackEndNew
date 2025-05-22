"""
Recommendation service.

This module provides services for content and user recommendations.
"""
import logging
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any

from fastapi import Depends, HTTPException, status, Request

from api.db.firestore import db
from api.models.user import User
from api.schemas.ai import CourseResponse, CourseModule, ResourceType
from api.schemas.user import UserProfile
from api.services.feed import FeedService
from api.services.user import UserService
from api.services.ai import AIService
from api.core.error_utils_ai import handle_ai_errors, graceful_ai_degradation
from api.core.errors_ai import RecommendationError, AIQuotaExceededError

logger = logging.getLogger(__name__)


class RecommendationService:
    """Recommendation service for users, content, and courses."""
    
    def __init__(
        self, 
        user_service: UserService = Depends(),
        feed_service: FeedService = Depends(),
        ai_service: AIService = Depends(),
    ):
        """
        Initialize recommendation service.
        
        Args:
            user_service: User service
            feed_service: Feed service
            ai_service: AI service
        """
        self.user_service = user_service
        self.feed_service = feed_service
        self.ai_service = ai_service
        self.db = db
    
    @handle_ai_errors
    async def get_recommended_users(
        self, 
        user_id: str, 
        limit: int = 10,
        exclude_following: bool = True
    ) -> List[UserProfile]:
        """
        Get personalized user recommendations for discovery.
        
        Uses multiple scoring factors:
        1. Network proximity (friends of friends)
        2. Content affinity (interests in similar content)
        3. User engagement (active users)
        4. Growth optimization (new users that need growth)
        
        Args:
            user_id: User ID
            limit: Maximum number of users to recommend
            exclude_following: Whether to exclude users that the user already follows
            
        Returns:
            List[UserProfile]: List of recommended users
            
        Raises:
            RecommendationError: If recommendation generation fails
            AIQuotaExceededError: If AI quota is exceeded
        """
        try:
            current_user = await self.user_service.get_by_id(user_id)
            if not current_user:
                return []
            
            # Get users the current user follows
            follows_ref = db.collection("follows").where("follower_id", "==", user_id)
            follows_docs = await follows_ref.get()
            
            following_ids = [doc.get("following_id") for doc in follows_docs]
            
            # 1. Friends of friends (network proximity)
            # Get users followed by users that the current user follows (2nd degree)
            friends_of_friends_ids = set()
            for following_id in following_ids:
                fof_ref = db.collection("follows").where("follower_id", "==", following_id)
                fof_docs = await fof_ref.get()
                for doc in fof_docs:
                    friend_id = doc.get("following_id")
                    if friend_id != user_id and (not exclude_following or friend_id not in following_ids):
                        friends_of_friends_ids.add(friend_id)
            
            # 2. Content affinity: users who create content similar to what the user has liked
            # Get content (posts) that the user has liked in the last 30 days
            now = datetime.utcnow()
            likes_ref = db.collection("likes").where(
                "user_id", "==", user_id
            ).where(
                "created_at", ">=", now - timedelta(days=30)
            ).limit(50)  # Limit to recent likes
            
            likes_docs = await likes_ref.get()
            
            # Extract post IDs and get the posts
            liked_post_ids = [doc.get("post_id") for doc in likes_docs]
            liked_posts = []
            author_content_match = {}  # Map of author_id -> content match score
            
            for post_id in liked_post_ids:
                post = await self.feed_service.get_post(post_id)
                if post and post.author_id != user_id:
                    liked_posts.append(post)
                    
                    # Increment score for author
                    if post.author_id not in author_content_match:
                        author_content_match[post.author_id] = 0
                    
                    # Authors with multiple appreciated posts get higher scores    
                    author_content_match[post.author_id] += 1
            
            # Normalize content match scores
            max_content_score = max(author_content_match.values()) if author_content_match else 1
            for author_id in author_content_match:
                author_content_match[author_id] /= max_content_score
            
            # 3. User engagement and 4. Growth potential
            # Get all potential users to recommend
            potential_users = []
            
            # Add friends of friends first (network proximity)
            for fof_id in friends_of_friends_ids:
                user = await self.user_service.get_by_id(fof_id)
                if user:
                    potential_users.append(user)
            
            # Add users with content affinity
            for author_id in author_content_match:
                if author_id not in friends_of_friends_ids and (not exclude_following or author_id not in following_ids):
                    user = await self.user_service.get_by_id(author_id)
                    if user and user not in potential_users:
                        potential_users.append(user)
            
            # If we still need more users, add some active users
            if len(potential_users) < limit * 2:  # Get more than we need for scoring
                # In a real system, we would get recently active users
                # For now, just get some random users
                all_users_ref = db.collection("users").limit(50)
                all_users_docs = await all_users_ref.get()
                
                for doc in all_users_docs:
                    user_data = doc.to_dict()
                    if doc.id != user_id and (not exclude_following or doc.id not in following_ids):
                        user = User.from_dict(user_data, doc.id)
                        if user and user not in potential_users:
                            potential_users.append(user)
            
            # Score and rank users for recommendation
            scored_users = []
            for user in potential_users:
                # Base score
                score = 0.0
                
                # Network proximity score (friends of friends)
                if user.id in friends_of_friends_ids:
                    score += 0.4
                
                # Content affinity score
                if user.id in author_content_match:
                    score += 0.4 * author_content_match[user.id]
                
                # User engagement score (based on activity)
                # In a real system, we'd use actual engagement metrics
                # For now, use followers count as a proxy
                followers = getattr(user, "followers_count", 0)
                engagement_score = min(0.8, math.log2(followers + 1) / 10) if followers > 0 else 0
                score += 0.2 * engagement_score
                
                # Growth potential
                # Slightly boost newer users with reasonable content
                days_since_creation = (now - user.created_at).days
                if 7 <= days_since_creation <= 60:  # 1 week to 2 months old
                    score += 0.1
                
                # Add randomness for exploration (up to 10%)
                score += random.random() * 0.1
                
                # Cap score at 1.0
                score = min(1.0, score)
                
                scored_users.append((user, score))
            
            # Sort by score and take top users
            scored_users.sort(key=lambda x: x[1], reverse=True)
            recommended_users = scored_users[:limit]
            
            # Build response
            result = []
            for user, _ in recommended_users:
                is_following = user.id in following_ids
                
                result.append(UserProfile(
                    id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    avatar_url=user.avatar_url,
                    bio=user.bio,
                    lang=user.lang,
                    followers_count=getattr(user, "followers_count", 0),
                    following_count=getattr(user, "following_count", 0),
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    is_active=user.is_active,
                    is_verified=user.is_verified,
                ))
            
            return result
        
        except Exception as e:
            logger.error(f"Error getting recommended users: {e}")
            return []
    
    @handle_ai_errors
    async def get_recommended_courses(
        self, 
        user_id: str, 
        limit: int = 5
    ) -> List[CourseResponse]:
        """
        Get personalized course recommendations with skill gap analysis.
        
        Uses multiple scoring factors:
        1. User interaction history (what content they've engaged with)
        2. Topic relevance to user's interests 
        3. Skill gap analysis based on user's profile and activity
        4. Content diversity to encourage exploration
        
        Raises:
            RecommendationError: If recommendation generation fails
            AIQuotaExceededError: If AI quota is exceeded
        
        Args:
            user_id: User ID
            limit: Maximum number of courses to recommend
            
        Returns:
            List[CourseResponse]: List of recommended courses
        """
        try:
            current_user = await self.user_service.get_by_id(user_id)
            if not current_user:
                return []
            
            # 1. Extract topics of interest from user's activity
            # Get posts the user has liked/commented on
            now = datetime.utcnow()
            likes_ref = db.collection("likes").where(
                "user_id", "==", user_id
            ).where(
                "created_at", ">=", now - timedelta(days=60)
            ).limit(50)
            
            likes_docs = await likes_ref.get()
            
            # Get post topics from liked posts
            topics_of_interest = {}  # Dict[topic, weight]
            
            for like_doc in likes_docs:
                post_id = like_doc.get("post_id")
                try:
                    post = await self.feed_service.get_post(post_id)
                    if post and post.tags:
                        for tag in post.tags:
                            if tag not in topics_of_interest:
                                topics_of_interest[tag] = 0
                            topics_of_interest[tag] += 1
                except Exception:
                    continue
            
            # 2. Find courses that already exist in the system
            all_courses_ref = db.collection("courses").limit(100)
            all_courses_docs = await all_courses_ref.get()
            
            # Score existing courses based on relevance
            scored_courses = []
            user_completed_courses = set()  # Courses the user has completed
            
            # In a real system, we'd track course completion
            # For now, we'll assume the user hasn't completed any courses
            
            # Get user's previously viewed courses
            user_course_views_ref = db.collection("user_course_views").where(
                "user_id", "==", user_id
            )
            user_course_views = await user_course_views_ref.get()
            user_viewed_courses = {doc.get("course_id") for doc in user_course_views}
            
            # Score courses by topic relevance
            for doc in all_courses_docs:
                course_data = doc.to_dict()
                course_id = doc.id
                
                # Skip courses created by the user
                if course_data.get("creator_id") == user_id:
                    continue
                
                # Skip completed courses
                if course_id in user_completed_courses:
                    continue
                
                # Base score
                score = 0.0
                
                # Extract topics from course
                course_topics = set()
                for module in course_data.get("modules", []):
                    # Extract keywords from module title and description
                    title_words = module.get("title", "").lower().split()
                    desc_words = module.get("description", "").lower().split()
                    
                    # Add non-trivial words as topics (simple approach)
                    for word in title_words + desc_words:
                        if len(word) > 4 and word not in ["about", "these", "those", "their", "there"]:
                            course_topics.add(word)
                
                # Score based on topic match
                for topic, weight in topics_of_interest.items():
                    topic_lower = topic.lower()
                    # Exact match
                    if topic_lower in course_topics:
                        score += 0.2 * weight
                    
                    # Partial match
                    for course_topic in course_topics:
                        if topic_lower in course_topic or course_topic in topic_lower:
                            score += 0.1 * weight
                            break
                
                # Boost courses in user's language
                if course_data.get("lang") == current_user.lang:
                    score += 0.1
                
                # Recency boost for newer courses
                created_at = course_data.get("created_at")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                        days_since_creation = (now - created_at).days
                        if days_since_creation < 30:
                            score += 0.1
                    except (ValueError, TypeError):
                        pass
                
                # Skill gap boost - prioritize courses with content not seen before
                # This is a simplified approach
                if course_id not in user_viewed_courses:
                    score += 0.15
                
                # Add randomness for exploration (up to 10%)
                score += random.random() * 0.1
                
                # Cap score at 1.0
                score = min(1.0, score)
                
                # Add course to scored list if it has a non-zero score
                if score > 0:
                    scored_courses.append((course_id, score, course_data))
            
            # Sort by score and take top courses
            scored_courses.sort(key=lambda x: x[1], reverse=True)
            top_courses = scored_courses[:limit]
            
            # Build response
            recommended_courses = []
            for course_id, _, course_data in top_courses:
                try:
                    # Create CourseResponse object
                    modules = []
                    for module_data in course_data.get("modules", []):
                        module = CourseModule(
                            title=module_data.get("title", ""),
                            description=module_data.get("description", ""),
                            resources=module_data.get("resources", []),
                            order=module_data.get("order", 0),
                        )
                        modules.append(module)
                    
                    course = CourseResponse(
                        id=course_id,
                        title=course_data.get("title", ""),
                        description=course_data.get("description", ""),
                        modules=modules,
                        created_at=course_data.get("created_at", ""),
                        updated_at=course_data.get("updated_at", ""),
                        creator_id=course_data.get("creator_id", ""),
                        lang=course_data.get("lang", "en-US"),
                    )
                    recommended_courses.append(course)
                except Exception as e:
                    logger.error(f"Error creating course response: {e}")
                    continue
            
            # 3. If we don't have enough courses, generate suggestions for new courses
            if len(recommended_courses) < limit:
                # Get top topics that don't have courses yet
                remaining_topics = sorted(
                    topics_of_interest.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )
                
                for topic, _ in remaining_topics:
                    if len(recommended_courses) >= limit:
                        break
                        
                    # Skip topics that already have courses
                    has_course = False
                    for course in recommended_courses:
                        if topic.lower() in course.title.lower() or topic.lower() in course.description.lower():
                            has_course = True
                            break
                    
                    if has_course:
                        continue
                    
                    try:
                        # In a real system, we could generate a sample course here
                        # For now, we'll just create a placeholder recommendation
                        modules = [
                            CourseModule(
                                title=f"Introduction to {topic}",
                                description=f"Learn the basics of {topic}",
                                resources=[],
                                order=1,
                            ),
                            CourseModule(
                                title=f"Advanced {topic}",
                                description=f"Deepen your knowledge of {topic}",
                                resources=[],
                                order=2,
                            ),
                        ]
                        
                        course = CourseResponse(
                            id=f"recommended-{topic.lower().replace(' ', '-')}",
                            title=f"{topic.title()} Mastery",
                            description=f"A comprehensive course on {topic} tailored to your interests",
                            modules=modules,
                            created_at=now.isoformat(),
                            updated_at=now.isoformat(),
                            creator_id="system",
                            lang=current_user.lang,
                        )
                        recommended_courses.append(course)
                    except Exception as e:
                        logger.error(f"Error creating placeholder course: {e}")
            
            return recommended_courses
        
        except Exception as e:
            logger.error(f"Error getting recommended courses: {e}")
            return []
