"""
Ads router.

This module defines the ad endpoints.
"""
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from api.core.security import get_current_user
from api.models.user import User
from api.schemas.ads import (
    Ad,
    AdAnalytics,
    AdCreate,
    AdPlacement,
    AdResponse,
    AdUpdate,
    AdsResponse,
)
from api.services.ads import AdService

router = APIRouter(prefix="/ads", tags=["ads"])


@router.post("", response_model=Ad, status_code=status.HTTP_201_CREATED)
async def create_ad(
    ad_create: AdCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Create a new ad.
    
    Args:
        ad_create: Ad creation data
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        Ad: Created ad
    """
    return await ad_service.create_ad(current_user.id, ad_create)


@router.get("", response_model=AdsResponse)
async def get_ads_by_advertiser(
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = None,
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Get ads by advertiser.
    
    Args:
        limit: Maximum number of ads to return
        cursor: Pagination cursor
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        AdsResponse: Ads response with pagination
    """
    ads = await ad_service.get_ads_by_advertiser(current_user.id, limit, cursor)
    
    # Create next cursor
    next_cursor = None
    if ads and len(ads) == limit:
        import base64
        
        last_ts = int(ads[-1].created_at.timestamp() * 1000)
        next_cursor = base64.b64encode(str(last_ts).encode()).decode()
    
    return AdsResponse(
        items=ads,
        next_cursor=next_cursor,
    )


@router.get("/{ad_id}", response_model=Ad)
async def get_ad(
    ad_id: str = Path(..., title="The ID of the ad to get"),
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Get ad by ID.
    
    Args:
        ad_id: Ad ID
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        Ad: Ad
        
    Raises:
        HTTPException: If ad not found
    """
    return await ad_service.get_ad(ad_id, current_user.id)


@router.patch("/{ad_id}", response_model=Ad)
async def update_ad(
    ad_update: AdUpdate,
    ad_id: str = Path(..., title="The ID of the ad to update"),
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Update ad.
    
    Args:
        ad_update: Ad update data
        ad_id: Ad ID
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        Ad: Updated ad
        
    Raises:
        HTTPException: If ad not found or not authorized
    """
    return await ad_service.update_ad(ad_id, current_user.id, ad_update)


@router.get("/{ad_id}/analytics", response_model=AdAnalytics)
async def get_ad_analytics(
    ad_id: str = Path(..., title="The ID of the ad to get analytics for"),
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Get ad analytics.
    
    Args:
        ad_id: Ad ID
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        AdAnalytics: Ad analytics
        
    Raises:
        HTTPException: If ad not found or not authorized
    """
    return await ad_service.get_ad_analytics(ad_id, current_user.id)


@router.post("/{ad_id}/impressions", response_model=Dict[str, str])
async def track_impression(
    ad_id: str = Path(..., title="The ID of the ad to track impression for"),
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Track ad impression.
    
    Args:
        ad_id: Ad ID
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        Dict[str, str]: Success response
        
    Raises:
        HTTPException: If ad not found
    """
    success = await ad_service.track_ad_impression(ad_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ad not found",
        )
        
    return {"status": "success"}


@router.post("/{ad_id}/clicks", response_model=Dict[str, str])
async def track_click(
    ad_id: str = Path(..., title="The ID of the ad to track click for"),
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Track ad click.
    
    Args:
        ad_id: Ad ID
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        Dict[str, str]: Success response
        
    Raises:
        HTTPException: If ad not found
    """
    success = await ad_service.track_ad_click(ad_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ad not found",
        )
        
    return {"status": "success"}


@router.get("/serve/{placement}", response_model=List[Ad])
async def serve_ads(
    placement: AdPlacement,
    current_user: Annotated[User, Depends(get_current_user)],
    ad_service: Annotated[AdService, Depends()],
):
    """
    Get ads for a specific placement.
    
    Args:
        placement: Ad placement
        current_user: Current authenticated user
        ad_service: Ad service
        
    Returns:
        List[Ad]: List of ads
    """
    return await ad_service.get_ads_for_placement(placement, current_user.id)
