"""
Forecasting API endpoint.
"""

from fastapi import APIRouter, HTTPException, Query

from src.bandit_ads.utils import get_logger

logger = get_logger('api.forecasting')
router = APIRouter()


@router.get("/{campaign_id}")
async def get_forecast(
    campaign_id: int,
    horizon: int = Query(30, ge=7, le=90, description="Forecast horizon in days"),
):
    """
    Return projected ROAS and revenue for a campaign over the given horizon.

    Uses historical Metric records + Thompson Sampling posteriors to build
    channel-level forecasts with confidence bands.
    """
    try:
        from src.bandit_ads.forecasting import ROIForecaster
        forecaster = ROIForecaster()
        return forecaster.forecast(campaign_id=campaign_id, horizon_days=horizon)
    except Exception as e:
        logger.error(f"Forecasting error for campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
