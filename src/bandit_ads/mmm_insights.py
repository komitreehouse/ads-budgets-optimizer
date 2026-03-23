"""
MMM Insights Engine

Computes media mix model insights from historical Metric data:
- Channel contribution and efficiency scores
- Diminishing returns / saturation curves (log-linear response model)
- Optimal budget allocation recommendations
- Cross-campaign holistic view

Uses actual DB data; falls back to stubs when DB is empty.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.bandit_ads.utils import get_logger

logger = get_logger("mmm_insights")

# Diminishing-returns shape parameters per channel type (alpha in log model)
# Higher alpha = faster saturation
CHANNEL_ALPHA = {
    "Google Search":   0.55,
    "Meta Social":     0.45,
    "Programmatic":    0.35,
    "Display":         0.30,
    "Video":           0.40,
    "Email":           0.20,
    "Affiliate":       0.25,
}
DEFAULT_ALPHA = 0.40


class MMMInsightsEngine:
    """Generates MMM insights from historical spend/revenue data."""

    def __init__(self):
        try:
            from src.bandit_ads.database import get_db_manager
            self.db_manager = get_db_manager()
        except Exception:
            self.db_manager = None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def get_channel_summary(
        self,
        campaign_id: Optional[int] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Per-channel spend/revenue/ROAS/saturation summary.

        Returns a list of dicts sorted by spend descending:
        {channel, spend, revenue, roas, impressions, clicks,
         conversions, saturation_score, efficiency_score,
         marginal_roas, recommendation}
        """
        rows = self._load_metrics(campaign_id, days)
        if not rows:
            return self._stub_channel_summary()
        return self._compute_channel_summary(rows)

    def get_saturation_curves(
        self,
        campaign_id: Optional[int] = None,
        days: int = 30,
        points: int = 20,
    ) -> Dict[str, Any]:
        """
        Diminishing-returns curves for each channel.

        Returns:
            {channel: {spend_points: [...], roas_points: [...],
                       current_spend: float, optimal_spend: float}}
        """
        rows = self._load_metrics(campaign_id, days)
        if not rows:
            return self._stub_saturation_curves(points)

        channel_data = self._aggregate_by_channel(rows)
        result = {}
        for ch, agg in channel_data.items():
            result[ch] = self._build_saturation_curve(
                ch, agg["spend"], agg["roas"], points
            )
        return result

    def get_budget_recommendations(
        self,
        campaign_id: Optional[int] = None,
        total_budget: Optional[float] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Optimal budget allocation across channels using equalised marginal ROAS.

        Returns:
            {total_budget, channels: {name: {current_spend, recommended_spend,
                                             change_pct, projected_roas,
                                             current_roas, rationale}},
             projected_blended_roas, current_blended_roas, roas_uplift_pct}
        """
        rows = self._load_metrics(campaign_id, days)
        if not rows:
            return self._stub_budget_recommendations(total_budget)

        channel_data = self._aggregate_by_channel(rows)
        total = total_budget or sum(v["spend"] for v in channel_data.values())
        return self._optimise_allocation(channel_data, total)

    def get_cross_platform_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Holistic view across all campaigns and channels.

        Returns aggregated efficiency matrix and top insights.
        """
        rows = self._load_metrics(campaign_id=None, days=days)
        if not rows:
            return self._stub_cross_platform()

        channel_data = self._aggregate_by_channel(rows)
        total_spend = sum(v["spend"] for v in channel_data.values())
        total_revenue = sum(v["revenue"] for v in channel_data.values())

        channels = self._compute_channel_summary(rows)
        insights = self._generate_insights(channels, total_spend)

        return {
            "total_spend": total_spend,
            "total_revenue": total_revenue,
            "blended_roas": total_revenue / total_spend if total_spend > 0 else 0,
            "channels": channels,
            "insights": insights,
            "days": days,
        }

    # -----------------------------------------------------------------------
    # Internal computation helpers
    # -----------------------------------------------------------------------

    def _load_metrics(
        self, campaign_id: Optional[int], days: int
    ) -> List[Dict]:
        """Load Metric rows from DB and return as list of plain dicts."""
        if not self.db_manager:
            return []
        try:
            from src.bandit_ads.database import Metric, Arm, Campaign
            cutoff = datetime.utcnow() - timedelta(days=days)
            with self.db_manager.get_session() as session:
                q = (
                    session.query(Metric, Arm)
                    .join(Arm, Metric.arm_id == Arm.id)
                    .filter(Metric.timestamp >= cutoff)
                )
                if campaign_id is not None:
                    q = q.filter(Arm.campaign_id == campaign_id)
                rows = []
                for metric, arm in q.all():
                    rows.append({
                        "channel": arm.name,
                        "spend": float(metric.cost or 0),
                        "revenue": float(metric.revenue or 0),
                        "impressions": int(metric.impressions or 0),
                        "clicks": int(metric.clicks or 0),
                        "conversions": int(metric.conversions or 0),
                        "timestamp": metric.timestamp,
                    })
                return rows
        except Exception as e:
            logger.warning(f"Could not load metrics from DB: {e}")
            return []

    def _aggregate_by_channel(self, rows: List[Dict]) -> Dict[str, Dict]:
        agg: Dict[str, Dict] = {}
        for r in rows:
            ch = r["channel"]
            if ch not in agg:
                agg[ch] = {"spend": 0, "revenue": 0, "impressions": 0,
                            "clicks": 0, "conversions": 0, "days": set()}
            agg[ch]["spend"] += r["spend"]
            agg[ch]["revenue"] += r["revenue"]
            agg[ch]["impressions"] += r["impressions"]
            agg[ch]["clicks"] += r["clicks"]
            agg[ch]["conversions"] += r["conversions"]
            if r.get("timestamp"):
                agg[ch]["days"].add(r["timestamp"].date())
        # Compute derived
        for ch, v in agg.items():
            v["roas"] = v["revenue"] / v["spend"] if v["spend"] > 0 else 0
            v["cpa"] = v["spend"] / v["conversions"] if v["conversions"] > 0 else 0
            v["ctr"] = v["clicks"] / v["impressions"] if v["impressions"] > 0 else 0
            v["cvr"] = v["conversions"] / v["clicks"] if v["clicks"] > 0 else 0
            v["active_days"] = len(v["days"])
        return agg

    def _compute_channel_summary(self, rows: List[Dict]) -> List[Dict[str, Any]]:
        channel_data = self._aggregate_by_channel(rows)
        total_spend = sum(v["spend"] for v in channel_data.values())
        total_revenue = sum(v["revenue"] for v in channel_data.values())
        avg_roas = total_revenue / total_spend if total_spend > 0 else 1.0

        result = []
        for ch, v in channel_data.items():
            spend = v["spend"]
            roas = v["roas"]
            alpha = CHANNEL_ALPHA.get(ch, DEFAULT_ALPHA)

            # Saturation: how close is marginal ROAS to zero?
            # Model: revenue = k * spend^alpha => marginal ROAS = alpha * roas
            marginal_roas = alpha * roas if spend > 0 else roas
            # Saturation score 0-1: 1 = fully saturated
            saturation = max(0, min(1, 1 - (marginal_roas / (avg_roas * 1.5))))

            # Efficiency: ROAS relative to portfolio average
            efficiency = roas / avg_roas if avg_roas > 0 else 1.0

            # Recommendation
            if saturation > 0.75:
                rec = "Reduce spend — approaching saturation"
            elif saturation < 0.35 and efficiency > 1.1:
                rec = "Increase spend — high marginal return available"
            elif efficiency < 0.7:
                rec = "Review creative/targeting — below-average efficiency"
            else:
                rec = "Maintain — performing near optimal"

            result.append({
                "channel": ch,
                "spend": spend,
                "revenue": v["revenue"],
                "roas": roas,
                "impressions": v["impressions"],
                "clicks": v["clicks"],
                "conversions": v["conversions"],
                "cpa": v["cpa"],
                "ctr": v["ctr"],
                "cvr": v["cvr"],
                "saturation_score": round(saturation, 3),
                "efficiency_score": round(efficiency, 3),
                "marginal_roas": round(marginal_roas, 3),
                "share_of_spend": round(spend / total_spend, 3) if total_spend > 0 else 0,
                "recommendation": rec,
            })

        return sorted(result, key=lambda x: x["spend"], reverse=True)

    def _build_saturation_curve(
        self, channel: str, current_spend: float, current_roas: float, points: int
    ) -> Dict:
        alpha = CHANNEL_ALPHA.get(channel, DEFAULT_ALPHA)
        # Estimate k from observed point: roas = k / spend^(1-alpha)
        # => revenue = k * spend^alpha  =>  k = revenue / spend^alpha
        revenue = current_spend * current_roas
        if current_spend <= 0:
            current_spend = 1000
        k = revenue / (current_spend ** alpha) if current_spend > 0 else 1

        # Curve from 20% to 200% of current spend
        min_s = current_spend * 0.2
        max_s = current_spend * 2.0
        step = (max_s - min_s) / (points - 1)

        spend_pts = [min_s + i * step for i in range(points)]
        roas_pts = [(k * (s ** alpha)) / s if s > 0 else 0 for s in spend_pts]

        # Optimal spend = where marginal ROAS = 1 (break-even on incremental $)
        # marginal revenue = k * alpha * s^(alpha-1) = 1 => s = (k*alpha)^(1/(1-alpha))
        try:
            optimal_spend = (k * alpha) ** (1 / (1 - alpha))
        except Exception:
            optimal_spend = current_spend

        return {
            "spend_points": [round(s, 2) for s in spend_pts],
            "roas_points": [round(r, 4) for r in roas_pts],
            "current_spend": round(current_spend, 2),
            "current_roas": round(current_roas, 4),
            "optimal_spend": round(optimal_spend, 2),
            "saturation_pct": round(min(100, current_spend / optimal_spend * 100), 1)
            if optimal_spend > 0 else 50,
        }

    def _optimise_allocation(
        self, channel_data: Dict[str, Dict], total_budget: float
    ) -> Dict[str, Any]:
        """
        Equalise marginal ROAS across channels via iterative budget allocation.
        Simple greedy: allocate budget to channel with highest marginal ROAS.
        """
        channels = list(channel_data.keys())
        allocs = {ch: 0.0 for ch in channels}
        step = total_budget / 100  # 1% increments

        for _ in range(100):
            # Compute marginal ROAS for each channel at current alloc
            marginals = {}
            for ch in channels:
                a = CHANNEL_ALPHA.get(ch, DEFAULT_ALPHA)
                obs_roas = channel_data[ch]["roas"]
                obs_spend = channel_data[ch]["spend"]
                curr = allocs[ch] + step
                # Marginal ROAS ≈ alpha * roas(current) scaled by spend ratio
                ratio = (curr / obs_spend) ** (a - 1) if obs_spend > 0 else 1
                marginals[ch] = a * obs_roas * ratio

            best = max(marginals, key=marginals.get)
            allocs[best] += step

        # Compute current and projected blended ROAS
        current_blended = (
            sum(v["revenue"] for v in channel_data.values())
            / sum(v["spend"] for v in channel_data.values())
            if sum(v["spend"] for v in channel_data.values()) > 0
            else 0
        )

        result_channels = {}
        total_proj_revenue = 0
        for ch in channels:
            obs = channel_data[ch]
            rec_spend = allocs[ch]
            a = CHANNEL_ALPHA.get(ch, DEFAULT_ALPHA)
            # Project revenue with power law
            k = (obs["revenue"]) / (obs["spend"] ** a) if obs["spend"] > 0 else 1
            proj_rev = k * (rec_spend ** a) if rec_spend > 0 else 0
            proj_roas = proj_rev / rec_spend if rec_spend > 0 else 0
            total_proj_revenue += proj_rev

            change_pct = ((rec_spend - obs["spend"]) / obs["spend"] * 100) if obs["spend"] > 0 else 0
            if change_pct > 5:
                rationale = f"High marginal ROAS ({a * obs['roas']:.2f}x) — increase allocation"
            elif change_pct < -5:
                rationale = f"Approaching saturation — reallocate to better-performing channels"
            else:
                rationale = "Near-optimal — maintain current level"

            result_channels[ch] = {
                "current_spend": round(obs["spend"], 2),
                "recommended_spend": round(rec_spend, 2),
                "change_pct": round(change_pct, 1),
                "current_roas": round(obs["roas"], 3),
                "projected_roas": round(proj_roas, 3),
                "rationale": rationale,
            }

        proj_blended = total_proj_revenue / total_budget if total_budget > 0 else 0
        uplift = ((proj_blended - current_blended) / current_blended * 100) if current_blended > 0 else 0

        return {
            "total_budget": round(total_budget, 2),
            "channels": result_channels,
            "current_blended_roas": round(current_blended, 3),
            "projected_blended_roas": round(proj_blended, 3),
            "roas_uplift_pct": round(uplift, 1),
        }

    def _generate_insights(
        self, channels: List[Dict], total_spend: float
    ) -> List[str]:
        insights = []
        saturated = [c for c in channels if c["saturation_score"] > 0.7]
        undersaturated = [c for c in channels if c["saturation_score"] < 0.3 and c["efficiency_score"] > 1.1]
        top = max(channels, key=lambda c: c["roas"], default=None)
        bottom = min(channels, key=lambda c: c["roas"], default=None)

        if saturated:
            names = ", ".join(c["channel"] for c in saturated[:2])
            insights.append(f"**{names}** {'are' if len(saturated) > 1 else 'is'} approaching saturation — marginal returns are declining.")
        if undersaturated:
            names = ", ".join(c["channel"] for c in undersaturated[:2])
            insights.append(f"**{names}** {'have' if len(undersaturated) > 1 else 'has'} capacity for additional spend with strong marginal returns.")
        if top and bottom and top["roas"] > bottom["roas"] * 1.5:
            insights.append(
                f"Largest ROAS gap: **{top['channel']}** ({top['roas']:.2f}x) vs "
                f"**{bottom['channel']}** ({bottom['roas']:.2f}x). "
                f"Consider rebalancing toward {top['channel']}."
            )
        if not insights:
            insights.append("Portfolio looks balanced. Continue monitoring for saturation signals.")
        return insights

    # -----------------------------------------------------------------------
    # Stubs (used when DB is empty)
    # -----------------------------------------------------------------------

    def _stub_channel_summary(self) -> List[Dict]:
        base = [
            {"channel": "Google Search",  "spend": 18500, "revenue": 46250, "impressions": 420000, "clicks": 9800,  "conversions": 310, "saturation_score": 0.52, "efficiency_score": 1.18},
            {"channel": "Meta Social",    "spend": 12000, "revenue": 25200, "impressions": 580000, "clicks": 7200,  "conversions": 185, "saturation_score": 0.71, "efficiency_score": 0.99},
            {"channel": "Programmatic",   "spend": 8200,  "revenue": 14760, "impressions": 920000, "clicks": 3100,  "conversions": 88,  "saturation_score": 0.38, "efficiency_score": 0.85},
            {"channel": "Video",          "spend": 5500,  "revenue": 11550, "impressions": 210000, "clicks": 1800,  "conversions": 52,  "saturation_score": 0.29, "efficiency_score": 0.99},
        ]
        total_spend = sum(r["spend"] for r in base)
        recs = {
            "Google Search": "Maintain — performing near optimal",
            "Meta Social": "Reduce spend — approaching saturation",
            "Programmatic": "Increase spend — high marginal return available",
            "Video": "Increase spend — high marginal return available",
        }
        for r in base:
            r["roas"] = round(r["revenue"] / r["spend"], 3)
            r["cpa"] = round(r["spend"] / r["conversions"], 2)
            r["ctr"] = round(r["clicks"] / r["impressions"], 4)
            r["cvr"] = round(r["conversions"] / r["clicks"], 4)
            r["marginal_roas"] = round(CHANNEL_ALPHA.get(r["channel"], DEFAULT_ALPHA) * r["roas"], 3)
            r["share_of_spend"] = round(r["spend"] / total_spend, 3)
            r["recommendation"] = recs[r["channel"]]
        return base

    def _stub_saturation_curves(self, points: int) -> Dict:
        stubs = {
            "Google Search":  (18500, 2.50),
            "Meta Social":    (12000, 2.10),
            "Programmatic":   (8200,  1.80),
            "Video":          (5500,  2.10),
        }
        return {
            ch: self._build_saturation_curve(ch, spend, roas, points)
            for ch, (spend, roas) in stubs.items()
        }

    def _stub_budget_recommendations(self, total_budget: Optional[float]) -> Dict:
        total = total_budget or 44200
        return {
            "total_budget": total,
            "current_blended_roas": 2.22,
            "projected_blended_roas": 2.41,
            "roas_uplift_pct": 8.6,
            "channels": {
                "Google Search":  {"current_spend": 18500, "recommended_spend": round(total * 0.46, 2), "change_pct": 10.0, "current_roas": 2.50, "projected_roas": 2.55, "rationale": "High marginal ROAS — increase allocation"},
                "Meta Social":    {"current_spend": 12000, "recommended_spend": round(total * 0.22, 2), "change_pct": -18.3, "current_roas": 2.10, "projected_roas": 2.28, "rationale": "Approaching saturation — reallocate to better-performing channels"},
                "Programmatic":   {"current_spend": 8200,  "recommended_spend": round(total * 0.20, 2), "change_pct": 7.6,  "current_roas": 1.80, "projected_roas": 1.95, "rationale": "High marginal ROAS — increase allocation"},
                "Video":          {"current_spend": 5500,  "recommended_spend": round(total * 0.12, 2), "change_pct": -4.1, "current_roas": 2.10, "projected_roas": 2.12, "rationale": "Near-optimal — maintain current level"},
            },
        }

    def _stub_cross_platform(self) -> Dict:
        channels = self._stub_channel_summary()
        total_spend = sum(c["spend"] for c in channels)
        total_revenue = sum(c["revenue"] for c in channels)
        return {
            "total_spend": total_spend,
            "total_revenue": total_revenue,
            "blended_roas": round(total_revenue / total_spend, 3),
            "channels": channels,
            "insights": self._generate_insights(channels, total_spend),
            "days": 30,
        }
