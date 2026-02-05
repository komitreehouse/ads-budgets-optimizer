"""
Optimizer API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.bandit_ads.utils import get_logger

logger = get_logger('api.optimizer')
router = APIRouter()


@router.get("/status")
async def get_optimizer_status():
    """Get optimizer service status."""
    try:
        # TODO: Integrate with optimization service when available
        # For now, return mock status
        return {
            "status": "running",  # running, paused, stopped
            "last_run": datetime.utcnow().isoformat(),
            "next_run": (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
            "active_campaigns": 0,
            "total_decisions": 0,
            "success_rate": 1.0
        }
    except Exception as e:
        logger.error(f"Error getting optimizer status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions")
async def get_recent_decisions(
    limit: int = Query(5, description="Number of recent decisions to return"),
    campaign: Optional[str] = Query(None, description="Filter by campaign name"),
    decision_type: Optional[str] = Query(None, description="Filter by decision type")
):
    """Get recent optimization decisions."""
    try:
        # TODO: Integrate with change tracker/explainer when available
        return []
    except Exception as e:
        logger.error(f"Error getting decisions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/factor-attribution")
async def get_factor_attribution():
    """Get factor attribution for recent decisions."""
    try:
        # TODO: Integrate with explainer when available
        return []
    except Exception as e:
        logger.error(f"Error getting factor attribution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
