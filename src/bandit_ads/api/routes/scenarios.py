"""
Scenario planning API endpoint.
"""

from typing import Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.bandit_ads.utils import get_logger

logger = get_logger('api.scenarios')
router = APIRouter()


class SimulateRequest(BaseModel):
    campaign_id: int
    budget_changes: Dict[str, float]  # {channel_name: new_daily_budget}
    horizon_days: int = 30


@router.post("/simulate")
async def simulate_scenario(request: SimulateRequest):
    """
    Simulate what-if budget reallocation and return projected impact.

    Returns side-by-side comparison of current vs proposed plan over the
    specified horizon.
    """
    try:
        from src.bandit_ads.scenario_planner import ScenarioPlanner
        planner = ScenarioPlanner()
        return planner.simulate(
            campaign_id=request.campaign_id,
            budget_changes=request.budget_changes,
            horizon_days=request.horizon_days,
        )
    except Exception as e:
        logger.error(f"Scenario simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
