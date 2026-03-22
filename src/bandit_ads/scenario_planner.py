"""
Scenario Planner — simulates the effect of hypothetical budget reallocation.

Given a campaign and a set of proposed budget changes per channel, the planner
runs a lightweight projection using the current ROIForecaster and the bandit's
posterior estimates to produce a side-by-side comparison.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.bandit_ads.utils import get_logger
from src.bandit_ads.forecasting import ROIForecaster

logger = get_logger('scenario_planner')


class ScenarioPlanner:
    """
    Simulates 'what-if' budget reallocations and projects their impact.

    The simulation projects revenue and ROAS for both the current allocation
    and the proposed allocation, using the same forecasting engine so that
    seasonality and uncertainty are consistently applied.
    """

    def __init__(self):
        self.forecaster = ROIForecaster()

    def simulate(
        self,
        campaign_id: int,
        budget_changes: Dict[str, float],  # {channel: new_daily_budget}
        horizon_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Compare current plan vs proposed budget reallocation.

        Parameters
        ----------
        campaign_id : int
        budget_changes : dict
            Mapping of channel name → proposed daily budget (absolute dollars).
        horizon_days : int

        Returns
        -------
        {
            "campaign_id": int,
            "horizon_days": int,
            "current": {"total_spend": float, "total_revenue": float, "blended_roas": float,
                        "channels": {...}},
            "proposed": {"total_spend": float, "total_revenue": float, "blended_roas": float,
                         "channels": {...}},
            "delta": {"total_spend": float, "total_revenue": float, "roas_change_pct": float},
        }
        """
        forecast = self.forecaster.forecast(campaign_id, horizon_days=horizon_days)
        channels_forecast = forecast.get("channels", {})

        current_channels = self._project_channels(channels_forecast, override_budgets=None)
        proposed_channels = self._project_channels(channels_forecast, override_budgets=budget_changes)

        current_totals = self._aggregate(current_channels)
        proposed_totals = self._aggregate(proposed_channels)

        roas_delta_pct = 0.0
        if current_totals["blended_roas"] > 0:
            roas_delta_pct = (
                (proposed_totals["blended_roas"] - current_totals["blended_roas"])
                / current_totals["blended_roas"]
                * 100
            )

        return {
            "campaign_id": campaign_id,
            "horizon_days": horizon_days,
            "current": {**current_totals, "channels": current_channels},
            "proposed": {**proposed_totals, "channels": proposed_channels},
            "delta": {
                "total_spend": proposed_totals["total_spend"] - current_totals["total_spend"],
                "total_revenue": proposed_totals["total_revenue"] - current_totals["total_revenue"],
                "roas_change_pct": round(roas_delta_pct, 2),
            },
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _project_channels(
        self,
        channels_forecast: Dict[str, Any],
        override_budgets: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        """Build per-channel totals for the horizon, optionally overriding spend."""
        result: Dict[str, Any] = {}
        for ch, data in channels_forecast.items():
            base_spends = data.get("spend_projected", [])
            roas_means = data.get("roas_mean", [])

            if override_budgets and ch in override_budgets:
                new_daily = override_budgets[ch]
                spends = [new_daily] * len(base_spends)
            else:
                spends = base_spends

            total_spend = sum(spends)
            # Revenue = spend * projected ROAS for each day
            revenues = [s * r for s, r in zip(spends, roas_means)]
            total_revenue = sum(revenues)
            avg_roas = total_revenue / total_spend if total_spend > 0 else 0.0

            result[ch] = {
                "total_spend": round(total_spend, 2),
                "total_revenue": round(total_revenue, 2),
                "avg_roas": round(avg_roas, 3),
            }
        return result

    @staticmethod
    def _aggregate(channel_totals: Dict[str, Any]) -> Dict[str, float]:
        total_spend = sum(v["total_spend"] for v in channel_totals.values())
        total_revenue = sum(v["total_revenue"] for v in channel_totals.values())
        blended_roas = total_revenue / total_spend if total_spend > 0 else 0.0
        return {
            "total_spend": round(total_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "blended_roas": round(blended_roas, 3),
        }
