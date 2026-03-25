"""
MMM Insights API endpoints.

Uses MMMInsightsRouter which delegates to the Meridian engine when a trained
model is available, falling back to the rule-based MMMInsightsEngine otherwise.
"""

from fastapi import APIRouter, Query
from typing import Optional

from src.bandit_ads.utils import get_logger

logger = get_logger("api.mmm")
router = APIRouter()


def _get_engine(campaign_id: Optional[int] = None):
    """Resolve the best available MMM engine via the router."""
    from src.bandit_ads.meridian_insights import MMMInsightsRouter
    return MMMInsightsRouter(campaign_id=campaign_id)


@router.get("/cross-platform")
async def get_cross_platform_summary(days: int = Query(30)):
    """Holistic MMM view across all campaigns and channels."""
    try:
        engine = _get_engine()
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
        engine = _get_engine(campaign_id)
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
        engine = _get_engine(campaign_id)
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
        engine = _get_engine(campaign_id)
        return engine.get_budget_recommendations(
            campaign_id=campaign_id,
            total_budget=total_budget,
            days=days,
        )
    except Exception as e:
        logger.error(f"Error getting budget recommendations: {e}")
        return {}


@router.get("/training-status")
async def get_meridian_training_status(
    campaign_id: Optional[int] = Query(None),
):
    """Check whether a Meridian model is trained for a campaign."""
    try:
        from src.bandit_ads.meridian_trainer import MeridianTrainer
        trainer = MeridianTrainer()
        return trainer.get_training_status(campaign_id)
    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        return {"trained": False, "error": str(e)}


@router.post("/train")
async def trigger_meridian_training(
    campaign_id: Optional[int] = Query(None),
):
    """Manually trigger Meridian model training for a campaign."""
    try:
        from src.bandit_ads.meridian_trainer import MeridianTrainer
        trainer = MeridianTrainer()
        result = trainer.train(campaign_id=campaign_id)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error triggering training: {e}")
        return {"success": False, "error": str(e)}
