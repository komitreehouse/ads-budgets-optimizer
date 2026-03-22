"""
Attribution API route.
"""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/{campaign_id}")
async def get_attribution(
    campaign_id: int,
    method: str = Query("linear", description="last_touch | linear | time_decay"),
    days: int = Query(30, description="lookback window in days"),
):
    """Return multi-touch attribution breakdown for a campaign."""
    try:
        from src.bandit_ads.attribution import AttributionEngine
        engine = AttributionEngine()
        result = engine.calculate(campaign_id, method=method, days=days)
        return {"campaign_id": campaign_id, "method": method, "days": days, "channels": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
