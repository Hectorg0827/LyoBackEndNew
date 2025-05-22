"""
Ads service.

This module provides services for ad operations.
"""
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Set, Tuple, Any
import json
from collections import defaultdict

from fastapi import Depends, HTTPException, status, Request

from api.core.config import settings
from api.db.firestore import db
from api.db.redis import cache
from api.schemas.ads import (
    Ad,
    AdAnalytics,
    AdCreate,
    AdResponse,
    AdUpdate,
    AdPlacement,
    TargetingCriteria,
)
from api.core.error_utils_ai import handle_ai_errors, graceful_ai_degradation
from api.core.errors_ai import AlgorithmError, ModelExecutionError

logger = logging.getLogger(__name__)


class AdService:
    """
    Ad service with advanced personalization and targeting.
    
    Features:
    - Enhanced user targeting based on behavior and interests
    - Ad performance optimization using engagement metrics
    - Optimal ad placement selection
    - Ad fatigue prevention mechanisms
    - Seamless integration with content feed
    """
    
    async def create_ad(self, advertiser_id: str, ad_data: AdCreate) -> Ad:
        """
        Create a new ad.
        
        Args:
            advertiser_id: Advertiser user ID
            ad_data: Ad data
            
        Returns:
            Ad: Created ad
            
        Raises:
            HTTPException: On error
        """
        try:
            now = datetime.utcnow()
            
            # Create ad document
            ad_id = str(uuid.uuid4())
            
            ad = {
                "id": ad_id,
                "title": ad_data.title,
                "description": ad_data.description,
                "image_url": ad_data.image_url,
                "call_to_action": ad_data.call_to_action,
                "destination_url": ad_data.destination_url,
                "start_date": ad_data.start_date,
                "end_date": ad_data.end_date,
                "placements": [p.value for p in ad_data.placements],
                "advertiser_id": advertiser_id,
                "status": "pending",  # Start as pending until reviewed
                "budget": ad_data.budget,
                "bid_amount": ad_data.bid_amount,
                "daily_cap": ad_data.daily_cap,
                "total_cap": ad_data.total_cap,
                "impressions": 0,
                "clicks": 0,
                "created_at": now,
                "updated_at": now,
                "targeting": ad_data.targeting.model_dump() if ad_data.targeting else None,
            }
            
            # Save to Firestore
            await db.collection("ads").document(ad_id).set(ad)
            
            # In a real system, trigger a review process
            # await self._trigger_ad_review(ad_id)
            
            return Ad(**ad)
        except Exception as e:
            logger.error(f"Error creating ad: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create ad: {str(e)}",
            )
    
    async def update_ad(
        self, ad_id: str, advertiser_id: str, ad_data: AdUpdate
    ) -> Ad:
        """
        Update an ad.
        
        Args:
            ad_id: Ad ID
            advertiser_id: Advertiser user ID
            ad_data: Ad data
            
        Returns:
            Ad: Updated ad
            
        Raises:
            HTTPException: On error
        """
        try:
            # Get ad
            ad_ref = db.collection("ads").document(ad_id)
            ad_doc = await ad_ref.get()
            
            if not ad_doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Ad not found",
                )
                
            ad = ad_doc.to_dict()
            
            # Check ownership
            if ad.get("advertiser_id") != advertiser_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update this ad",
                )
                
            # Don't allow updating active ads (in a real system, might allow some fields)
            if ad.get("status") == "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot update active ads",
                )
                
            # Update fields
            update_data = ad_data.model_dump(exclude_unset=True)
            
            # Handle special fields
            if "placements" in update_data:
                update_data["placements"] = [p.value for p in update_data["placements"]]
                
            if "targeting" in update_data and update_data["targeting"]:
                update_data["targeting"] = update_data["targeting"].model_dump()
            
            # Set updated_at
            update_data["updated_at"] = datetime.utcnow()
            
            # Set status to pending for re-review
            update_data["status"] = "pending"
            
            # Update in Firestore
            await ad_ref.update(update_data)
            
            # Get updated ad
            updated_ad_doc = await ad_ref.get()
            updated_ad = updated_ad_doc.to_dict()
            
            # In a real system, trigger a review process
            # await self._trigger_ad_review(ad_id)
            
            return Ad(**updated_ad)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating ad: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update ad: {str(e)}",
            )
    
    async def get_ad(self, ad_id: str, advertiser_id: Optional[str] = None) -> Ad:
        """
        Get ad by ID.
        
        Args:
            ad_id: Ad ID
            advertiser_id: Advertiser user ID (optional, for access control)
            
        Returns:
            Ad: Ad
            
        Raises:
            HTTPException: If ad not found or not accessible
        """
        try:
            # Get ad
            ad_ref = db.collection("ads").document(ad_id)
            ad_doc = await ad_ref.get()
            
            if not ad_doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Ad not found",
                )
                
            ad = ad_doc.to_dict()
            
            # Check access if advertiser_id provided
            if advertiser_id and ad.get("advertiser_id") != advertiser_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this ad",
                )
                
            return Ad(**ad)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting ad: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get ad: {str(e)}",
            )
    
    async def get_ads_by_advertiser(
        self, advertiser_id: str, limit: int = 20, cursor: Optional[str] = None
    ) -> List[Ad]:
        """
        Get ads by advertiser.
        
        Args:
            advertiser_id: Advertiser user ID
            limit: Maximum number of ads to return
            cursor: Pagination cursor
            
        Returns:
            List[Ad]: List of ads
        """
        try:
            # Query ads
            query = (
                db.collection("ads")
                .where("advertiser_id", "==", advertiser_id)
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
            
            # Build response
            ads = []
            for doc in docs:
                ad_data = doc.to_dict()
                ads.append(Ad(**ad_data))
                
            return ads
        except Exception as e:
            logger.error(f"Error getting ads by advertiser: {e}")
            return []
    
    @graceful_ai_degradation(fallback_value=[])
    async def get_ads_for_placement(
        self, placement: AdPlacement, user_id: Optional[str] = None, context_tags: List[str] = None
    ) -> List[Ad]:
        """
        Get personalized ads for a specific placement.
        
        Enhanced ad selection algorithm that considers:
        1. Ad relevance to user interests and behavior
        2. Ad performance (CTR, conversion rate)
        3. Ad diversity to prevent repetitiveness
        4. User ad fatigue prevention
        5. Contextual relevance to current content
        6. Optimal placement strategy
        
        Args:
            placement: Ad placement
            user_id: User ID (optional, for targeting)
            context_tags: Tags from current context (optional, for contextual relevance)
            
        Returns:
            List[Ad]: List of personalized ads or empty list if personalization fails
            
        Raises:
            AlgorithmError: If ad selection algorithm fails but is caught by graceful degradation
        """
        try:
            # Query active ads for this placement
            query = (
                db.collection("ads")
                .where("status", "==", "active")
                .where("placements", "array_contains", placement.value)
            )
            
            # Execute query
            docs = await query.get()
            
            # Filter and score ads
            now = datetime.utcnow()
            valid_ads_with_scores = []
            
            for doc in docs:
                ad_data = doc.to_dict()
                
                # Check start and end dates
                start_date = ad_data.get("start_date")
                end_date = ad_data.get("end_date")
                
                if start_date and isinstance(start_date, datetime) and start_date > now:
                    continue
                    
                if end_date and isinstance(end_date, datetime) and end_date < now:
                    continue
                
                # Check caps
                daily_cap = ad_data.get("daily_cap")
                total_cap = ad_data.get("total_cap")
                impressions = ad_data.get("impressions", 0)
                
                if daily_cap:
                    # In a real implementation, track daily impressions separately
                    # For now, we'll assume that daily impressions = total impressions
                    if impressions >= daily_cap:
                        continue
                        
                if total_cap and impressions >= total_cap:
                    continue
                
                # Ad fatigue prevention - if user has seen this ad too many times recently, reduce its score
                ad_fatigue_factor = 1.0
                if user_id:
                    try:
                        # Check how many times user has seen this ad in the last 24 hours
                        ad_impression_key = f"ad_imp:{user_id}:{ad_data['id']}"
                        recent_impressions = await db.collection("ad_impressions").where(
                            "user_id", "==", user_id
                        ).where(
                            "ad_id", "==", ad_data['id']
                        ).where(
                            "created_at", ">=", now - timedelta(hours=24)
                        ).count().get()
                        
                        # First item in the response is the count
                        count = recent_impressions[0][0].value if recent_impressions else 0
                        
                        # Reduce score as impressions increase (diminishing returns curve)
                        ad_fatigue_factor = max(0.2, 1.0 - (count * 0.1))
                    except Exception as e:
                        logger.warning(f"Error checking ad fatigue: {e}")
                
                # Enhanced targeting check - returns both match and relevance score
                targeting = ad_data.get("targeting", {})
                matches, relevance_score = await self._check_targeting(targeting, user_id) if user_id else (True, 0.5)
                
                if not matches:
                    continue
                
                # Calculate ad performance factor based on CTR
                clicks = ad_data.get("clicks", 0)
                performance_factor = 1.0
                if impressions > 10:  # Need minimum sample size
                    ctr = clicks / impressions if impressions > 0 else 0
                    # Better performing ads get higher score, with diminishing returns
                    performance_factor = min(2.0, 1.0 + (ctr * 10))  # 10% CTR -> 2x score
                
                # Contextual relevance - how well ad matches current context
                contextual_factor = 1.0
                if context_tags and ad_data.get("tags"):
                    matching_tags = set(context_tags).intersection(set(ad_data.get("tags", [])))
                    contextual_factor += min(0.5, len(matching_tags) * 0.1)  # Up to 50% boost for context match
                
                # Bid amount as base score
                bid_amount = ad_data.get("bid_amount", 0.1)
                
                # Combined score for ad
                final_score = (
                    bid_amount * 
                    performance_factor * 
                    ad_fatigue_factor * 
                    relevance_score *
                    contextual_factor
                )
                
                valid_ads_with_scores.append((Ad(**ad_data), final_score))
            
            # Sort by final score
            valid_ads_with_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Apply diversity rules - don't show too many ads from same advertiser
            seen_advertisers = set()
            diversified_ads = []
            
            for ad, score in valid_ads_with_scores:
                # Limit to at most 2 ads from same advertiser
                advertiser_id = getattr(ad, "advertiser_id", None)
                if advertiser_id and advertiser_id in seen_advertisers and len(seen_advertisers) >= 2:
                    continue
                
                if advertiser_id:
                    seen_advertisers.add(advertiser_id)
                
                diversified_ads.append(ad)
                
                # Return no more than 3 ads
                if len(diversified_ads) >= 3:
                    break
            
            return diversified_ads
        
        except Exception as e:
            logger.error(f"Error getting ads for placement: {e}")
            return []
    
    async def track_ad_impression(self, ad_id: str) -> bool:
        """
        Track ad impression.
        
        Args:
            ad_id: Ad ID
            
        Returns:
            bool: True if successful
        """
        try:
            # Get ad
            ad_ref = db.collection("ads").document(ad_id)
            ad_doc = await ad_ref.get()
            
            if not ad_doc.exists:
                return False
                
            # Update impression count
            await ad_ref.update({
                "impressions": ad_doc.get("impressions", 0) + 1,
            })
            
            return True
        except Exception as e:
            logger.error(f"Error tracking ad impression: {e}")
            return False
    
    async def track_ad_click(self, ad_id: str) -> bool:
        """
        Track ad click.
        
        Args:
            ad_id: Ad ID
            
        Returns:
            bool: True if successful
        """
        try:
            # Get ad
            ad_ref = db.collection("ads").document(ad_id)
            ad_doc = await ad_ref.get()
            
            if not ad_doc.exists:
                return False
                
            # Update click count
            await ad_ref.update({
                "clicks": ad_doc.get("clicks", 0) + 1,
            })
            
            return True
        except Exception as e:
            logger.error(f"Error tracking ad click: {e}")
            return False
    
    async def get_ad_analytics(
        self, ad_id: str, advertiser_id: str
    ) -> AdAnalytics:
        """
        Get ad analytics.
        
        Args:
            ad_id: Ad ID
            advertiser_id: Advertiser user ID
            
        Returns:
            AdAnalytics: Ad analytics
            
        Raises:
            HTTPException: If ad not found or not accessible
        """
        try:
            # Get ad
            ad_ref = db.collection("ads").document(ad_id)
            ad_doc = await ad_ref.get()
            
            if not ad_doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Ad not found",
                )
                
            ad_data = ad_doc.to_dict()
            
            # Check access
            if ad_data.get("advertiser_id") != advertiser_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this ad",
                )
                
            # Get analytics data
            impressions = ad_data.get("impressions", 0)
            clicks = ad_data.get("clicks", 0)
            
            # Calculate metrics
            ctr = 0
            if impressions > 0:
                ctr = clicks / impressions * 100
                
            # In a real system, we would calculate more metrics
            # and include time-series data
            
            return AdAnalytics(
                id=ad_id,
                impressions=impressions,
                clicks=clicks,
                ctr=ctr,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting ad analytics: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get ad analytics: {str(e)}",
            )
    
    async def _check_targeting(self, targeting: Dict, user_id: str) -> Tuple[bool, float]:
        """
        Check if targeting criteria match user and calculate relevance score.
        
        Enhanced targeting based on:
        1. Demographic data (age, gender, location)
        2. User interests derived from content interactions
        3. User behavior patterns
        4. Look-alike modeling (similar users)
        5. Contextual relevance
        
        Args:
            targeting: Targeting criteria
            user_id: User ID
            
        Returns:
            Tuple[bool, float]: (matches, relevance_score) - True if targeting matches, and relevance score (0-1)
        """
        try:
            # Default: medium match for all users with some randomness
            base_relevance = 0.5 + (random.random() * 0.2)
            
            if not targeting:
                return True, base_relevance
                
            # Get user data
            user_ref = db.collection("users").document(user_id)
            user_doc = await user_ref.get()
            
            if not user_doc.exists:
                return False, 0.0
                
            user_data = user_doc.to_dict()
            
            # 1. Demographic matching
            demo_match_score = 0.0
            demo_criteria_count = 0
            
            # Check location
            if "locations" in targeting and targeting["locations"]:
                demo_criteria_count += 1
                user_location = user_data.get("location", "").lower()
                if user_location:
                    for location in targeting["locations"]:
                        if location.lower() in user_location or user_location in location.lower():
                            demo_match_score += 1.0
                            break
            
            # Check language
            if "languages" in targeting and targeting["languages"]:
                demo_criteria_count += 1
                user_lang = user_data.get("lang", "").lower()
                if user_lang:
                    for language in targeting["languages"]:
                        if language.lower() == user_lang:
                            demo_match_score += 1.0
                            break
            
            # Normalize demographic match score
            if demo_criteria_count > 0:
                demo_match_score /= demo_criteria_count
            else:
                demo_match_score = 1.0  # No demographic criteria specified
            
            # 2. Interest matching based on user activity
            interest_match_score = 0.0
            
            if "interests" in targeting and targeting["interests"]:
                # Get user's recent activity (likes, comments, views)
                now = datetime.utcnow()
                likes_ref = db.collection("likes").where(
                    "user_id", "==", user_id
                ).where(
                    "created_at", ">=", now - timedelta(days=30)
                ).limit(50)
                
                likes_docs = await likes_ref.get()
                
                # Extract post IDs and get the posts
                user_interests = set()
                for doc in likes_docs:
                    post_id = doc.get("post_id")
                    try:
                        post_ref = db.collection("posts").document(post_id)
                        post_doc = await post_ref.get()
                        if post_doc.exists:
                            post_data = post_doc.to_dict()
                            tags = post_data.get("tags", [])
                            user_interests.update(tags)
                    except Exception:
                        pass
                
                # Check how many targeted interests match user interests
                if user_interests:
                    matched_interests = 0
                    for interest in targeting["interests"]:
                        interest_lower = interest.lower()
                        for user_interest in user_interests:
                            if (interest_lower == user_interest.lower() or
                                interest_lower in user_interest.lower() or
                                user_interest.lower() in interest_lower):
                                matched_interests += 1
                                break
                    
                    interest_match_score = min(1.0, matched_interests / len(targeting["interests"]))
                else:
                    # If we can't determine interests, use a moderate match probability
                    interest_match_score = 0.5
            else:
                # No interest targeting specified
                interest_match_score = 1.0
            
            # 3. Behavioral targeting (simplified version)
            behavior_match_score = 0.0
            
            if "behaviors" in targeting and targeting["behaviors"]:
                # In a real system, this would check user behaviors like:
                # - Purchase history
                # - App usage patterns
                # - Conversion history
                # For now, just use a random score
                behavior_match_score = random.random()
            else:
                # No behavior targeting specified
                behavior_match_score = 1.0
            
            # 4. Contextual relevance (based on current session)
            # This would typically use current session data
            # For now, just use a high default score
            context_match_score = 0.8
            
            # Calculate final match score with weights
            # Weight demographic and interest targeting more heavily
            final_score = (
                0.35 * demo_match_score +
                0.35 * interest_match_score +
                0.20 * behavior_match_score +
                0.10 * context_match_score
            )
            
            # Apply thresholds and randomization
            # Random element to explore wider audience occasionally
            exploration_factor = random.random() * 0.2
            
            # Match if score exceeds threshold or random exploration
            matches = (final_score > 0.6) or (final_score > 0.4 and random.random() < 0.2)
            
            return matches, final_score
            
        except Exception as e:
            logger.error(f"Error in enhanced targeting: {e}")
            # Fall back to basic targeting
            return random.random() < 0.7, 0.5
