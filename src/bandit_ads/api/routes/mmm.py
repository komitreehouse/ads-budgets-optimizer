"""
MMM Insights API endpoints.
"""

from fastapi import APIRouter, Query
from typing import Optional

from src.bandit_ads.utils import get_logger

logger = get_logger("api.mmm")
router = APIRouter()


@router.get("/cross-platform")
async def get_cross_platform_summary(days: int = Query(30)):
    """Holistic MMM view across all campaigns and channels."""
    try:
        from src.bandit_ads.mmm_insights import MMMInsightsEngine
        engine = MMMInsightsEngine()
        return engine.get_cross_platform_summary(days=days)
    except Exception as e:
        logger.error(f"Error getting cross-platform summary: {e}")
        return {}


@router.get("/{campaign_id}/channel-summary")
async def get_channel_summary(
    campaign_id: int,
    days: int = Query(30),
):
    """Per-channel spend/ROAS/saturation summary for a campaign."""
    try:
        from src.bandit_ads.mmm_insights import MMMInsightsEngine
        engine = MMMInsightsEngine()
        return engine.get_channel_summary(campaign_id=campaign_id, days=days)
    except Exception as e:
        logger.error(f"Error getting channel summary: {e}")
        return []


@router.get("/{campaign_id}/saturation-curves")
async def get_saturation_curves(
    campaign_id: int,
    days: int = Query(30),
    points: int = Query(20),
):
    """Diminishing-returns saturation curves per channel."""
    try:
        from src.bandit_ads.mmm_insights import MMMInsightsEngine
        engine = MMMInsightsEngine()
        return engine.get_saturation_curves(campaign_id=campaign_id, days=days, points=points)
    except Exception as e:
        logger.error(f"Error getting saturation curves: {e}")
        return {}


@router.get("/{campaign_id}/budget-recommendations")
async def get_budget_recommendations(
    campaign_id: int,
    total_budget: Optional[float] = Query(None),
    days: int = Query(30),
):
    """Optimal budget allocation recommendations."""
    try:
        from src.bandit_ads.mmm_insights import MMMInsightsEngine
        engine = MMMInsightsEngine()
        return engine.get_budget_recommendations(
            campaign_id=campaign_id,
            total_budget=total_budget,
            days=days,
        )
    except Exception as e:
        logger.error(f"Error getting budget recommendations: {e}")
        return {}
