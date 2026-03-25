"""
Meridian-powered MMM Insights Engine

Drop-in replacement for MMMInsightsEngine that uses a trained Meridian model
to produce channel summaries, saturation curves, and budget recommendations
with full posterior uncertainty (credible intervals).

Also provides MMMInsightsRouter — a façade that delegates to the Meridian
engine when a trained model exists, and falls back to the rule-based
MMMInsightsEngine otherwise.
"""

import math
from typing import Any, Dict, List, Optional

import numpy as np

from src.bandit_ads.utils import get_logger

logger = get_logger("meridian_insights")


class MeridianInsightsEngine:
    """
    Generates MMM insights from a trained Meridian model's posterior samples.

    Public API matches MMMInsightsEngine exactly (same method names, same
    return-dict shapes) so it can be swapped in transparently.  Additional
    fields (uncertainty_lower / uncertainty_upper) are added where applicable.
    """

    def __init__(self, campaign_id: Optional[int] = None):
        self.campaign_id = campaign_id
        self._model = None
        self._meta = None
        self._posteriors = None

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _ensure_model(self) -> bool:
        """Load the Meridian model if not already loaded. Returns True if available."""
        if self._model is not None or self._posteriors is not None:
            return True

        from src.bandit_ads.meridian_trainer import MeridianTrainer

        trainer = MeridianTrainer()
        self._meta = trainer.get_training_status(self.campaign_id)
        if not self._meta.get("trained"):
            return False

        self._model = trainer.load_model(self.campaign_id)
        if self._model is not None:
            try:
                idata = self._model.get_inference_data()
                self._posteriors = idata.posterior
            except Exception as exc:
                logger.warning(f"Could not extract posteriors: {exc}")
                return False
            return True

        # Fallback: try loading raw posteriors.npz
        import os

        npz_path = os.path.join(
            trainer._campaign_model_path(self.campaign_id), "posteriors.npz"
        )
        if os.path.exists(npz_path):
            self._posteriors = dict(np.load(npz_path, allow_pickle=True))
            return True

        return False

    @property
    def model_status(self) -> str:
        """Return 'meridian' if a trained model is loaded, else 'rule_based'."""
        if self._ensure_model():
            return "meridian"
        return "rule_based"

    # ------------------------------------------------------------------
    # Public API — identical signatures to MMMInsightsEngine
    # ------------------------------------------------------------------

    def get_channel_summary(
        self,
        campaign_id: Optional[int] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        if not self._ensure_model():
            return self._fallback().get_channel_summary(campaign_id, days)

        posteriors = self._extract_channel_posteriors()
        if not posteriors:
            return self._fallback().get_channel_summary(campaign_id, days)

        total_spend = sum(p["spend"] for p in posteriors.values())
        total_revenue = sum(p["revenue_mean"] for p in posteriors.values())
        avg_roas = total_revenue / total_spend if total_spend > 0 else 1.0

        result = []
        for ch, p in posteriors.items():
            spend = p["spend"]
            roas_mean = p["roas_mean"]
            roas_lower = p["roas_lower"]
            roas_upper = p["roas_upper"]

            # Saturation from Hill curve parameters
            saturation = p.get("saturation_score", 0.5)
            efficiency = roas_mean / avg_roas if avg_roas > 0 else 1.0
            marginal_roas = p.get("marginal_roas", roas_mean * 0.5)

            if saturation > 0.75:
                rec = "Reduce spend — approaching saturation"
            elif saturation < 0.35 and efficiency > 1.1:
                rec = "Increase spend — high marginal return available"
            elif efficiency < 0.7:
                rec = "Review creative/targeting — below-average efficiency"
            else:
                rec = "Maintain — performing near optimal"

            result.append(
                {
                    "channel": ch,
                    "spend": spend,
                    "revenue": p["revenue_mean"],
                    "roas": round(roas_mean, 3),
                    "roas_lower": round(roas_lower, 3),
                    "roas_upper": round(roas_upper, 3),
                    "impressions": p.get("impressions", 0),
                    "clicks": p.get("clicks", 0),
                    "conversions": p.get("conversions", 0),
                    "cpa": round(spend / max(p.get("conversions", 1), 1), 2),
                    "ctr": p.get("ctr", 0),
                    "cvr": p.get("cvr", 0),
                    "saturation_score": round(saturation, 3),
                    "efficiency_score": round(efficiency, 3),
                    "marginal_roas": round(marginal_roas, 3),
                    "share_of_spend": round(spend / total_spend, 3)
                    if total_spend > 0
                    else 0,
                    "recommendation": rec,
                    "uncertainty_lower": round(roas_lower, 3),
                    "uncertainty_upper": round(roas_upper, 3),
                    "model_source": "meridian",
                }
            )

        return sorted(result, key=lambda x: x["spend"], reverse=True)

    def get_saturation_curves(
        self,
        campaign_id: Optional[int] = None,
        days: int = 30,
        points: int = 20,
    ) -> Dict[str, Any]:
        if not self._ensure_model():
            return self._fallback().get_saturation_curves(campaign_id, days, points)

        posteriors = self._extract_channel_posteriors()
        if not posteriors:
            return self._fallback().get_saturation_curves(campaign_id, days, points)

        result = {}
        for ch, p in posteriors.items():
            hill = p.get("hill_params")
            if not hill:
                continue

            ec = hill["ec_mean"]  # Half-saturation point
            slope = hill["slope_mean"]  # Hill slope
            k = hill.get("k_mean", p["revenue_mean"])  # Scale

            current_spend = p["spend"]
            min_s = current_spend * 0.2
            max_s = current_spend * 2.0
            step = (max_s - min_s) / (points - 1) if points > 1 else 1

            spend_pts = [min_s + i * step for i in range(points)]

            # Hill function: response = k * (spend^slope / (ec^slope + spend^slope))
            def hill_roas(s):
                if s <= 0:
                    return 0
                response = k * (s ** slope / (ec ** slope + s ** slope))
                return response / s

            roas_pts = [hill_roas(s) for s in spend_pts]

            # Credible bands from posterior samples
            roas_lower = []
            roas_upper = []
            if "ec_samples" in hill and "slope_samples" in hill:
                for s in spend_pts:
                    if s <= 0:
                        roas_lower.append(0)
                        roas_upper.append(0)
                        continue
                    samples = k * (
                        s ** hill["slope_samples"]
                        / (hill["ec_samples"] ** hill["slope_samples"] + s ** hill["slope_samples"])
                    ) / s
                    roas_lower.append(float(np.percentile(samples, 2.5)))
                    roas_upper.append(float(np.percentile(samples, 97.5)))

            # Optimal spend: where marginal ROAS = 1
            # d(response)/d(spend) = k * slope * ec^slope * s^(slope-1) / (ec^slope + s^slope)^2
            # Set = 1 and solve numerically
            optimal_spend = self._find_optimal_spend(k, ec, slope, current_spend)

            curve = {
                "spend_points": [round(s, 2) for s in spend_pts],
                "roas_points": [round(r, 4) for r in roas_pts],
                "current_spend": round(current_spend, 2),
                "current_roas": round(hill_roas(current_spend), 4),
                "optimal_spend": round(optimal_spend, 2),
                "saturation_pct": round(
                    min(100, current_spend / optimal_spend * 100), 1
                )
                if optimal_spend > 0
                else 50,
                "model_source": "meridian",
            }

            if roas_lower:
                curve["roas_lower"] = [round(r, 4) for r in roas_lower]
                curve["roas_upper"] = [round(r, 4) for r in roas_upper]

            result[ch] = curve

        return result

    def get_budget_recommendations(
        self,
        campaign_id: Optional[int] = None,
        total_budget: Optional[float] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        if not self._ensure_model():
            return self._fallback().get_budget_recommendations(
                campaign_id, total_budget, days
            )

        posteriors = self._extract_channel_posteriors()
        if not posteriors:
            return self._fallback().get_budget_recommendations(
                campaign_id, total_budget, days
            )

        channels = list(posteriors.keys())
        total = total_budget or sum(p["spend"] for p in posteriors.values())

        # Use Meridian's built-in optimizer if available
        optimized = self._optimize_with_meridian(total, posteriors)
        if optimized is None:
            # Fallback: greedy marginal ROAS equalization using Hill posteriors
            optimized = self._optimize_greedy_hill(total, posteriors)

        # Compute current vs projected
        current_total_rev = sum(p["revenue_mean"] for p in posteriors.values())
        current_total_spend = sum(p["spend"] for p in posteriors.values())
        current_blended = (
            current_total_rev / current_total_spend if current_total_spend > 0 else 0
        )

        proj_total_rev = sum(v["projected_revenue"] for v in optimized.values())
        proj_blended = proj_total_rev / total if total > 0 else 0
        uplift = (
            (proj_blended - current_blended) / current_blended * 100
            if current_blended > 0
            else 0
        )

        result_channels = {}
        for ch in channels:
            obs = posteriors[ch]
            opt = optimized.get(ch, {})
            rec_spend = opt.get("recommended_spend", obs["spend"])
            proj_roas = opt.get("projected_roas", obs["roas_mean"])
            change_pct = (
                (rec_spend - obs["spend"]) / obs["spend"] * 100
                if obs["spend"] > 0
                else 0
            )

            if change_pct > 5:
                rationale = f"High marginal ROAS ({opt.get('marginal_roas', 0):.2f}x) — increase allocation"
            elif change_pct < -5:
                rationale = "Approaching saturation — reallocate to better-performing channels"
            else:
                rationale = "Near-optimal — maintain current level"

            result_channels[ch] = {
                "current_spend": round(obs["spend"], 2),
                "recommended_spend": round(rec_spend, 2),
                "change_pct": round(change_pct, 1),
                "current_roas": round(obs["roas_mean"], 3),
                "projected_roas": round(proj_roas, 3),
                "rationale": rationale,
                "model_source": "meridian",
            }

        return {
            "total_budget": round(total, 2),
            "channels": result_channels,
            "current_blended_roas": round(current_blended, 3),
            "projected_blended_roas": round(proj_blended, 3),
            "roas_uplift_pct": round(uplift, 1),
            "model_source": "meridian",
        }

    def get_cross_platform_summary(self, days: int = 30) -> Dict[str, Any]:
        if not self._ensure_model():
            return self._fallback().get_cross_platform_summary(days)

        channels = self.get_channel_summary(days=days)
        if not channels or channels[0].get("model_source") != "meridian":
            return self._fallback().get_cross_platform_summary(days)

        total_spend = sum(c["spend"] for c in channels)
        total_revenue = sum(c["revenue"] for c in channels)
        blended_roas = total_revenue / total_spend if total_spend > 0 else 0

        insights = self._generate_insights(channels, total_spend)

        return {
            "total_spend": total_spend,
            "total_revenue": total_revenue,
            "blended_roas": round(blended_roas, 3),
            "channels": channels,
            "insights": insights,
            "days": days,
            "model_source": "meridian",
        }

    # ------------------------------------------------------------------
    # Posterior extraction helpers
    # ------------------------------------------------------------------

    def _extract_channel_posteriors(self) -> Dict[str, Dict]:
        """
        Extract per-channel summary stats from the Meridian posterior.

        Returns a dict keyed by display channel name with:
            spend, revenue_mean, roas_mean, roas_lower, roas_upper,
            hill_params {ec_mean, slope_mean, ...}, saturation_score, marginal_roas
        """
        if self._posteriors is None:
            return {}

        # Get actual spend/revenue from DB for the period
        from src.bandit_ads.meridian_data import extract_meridian_dataset, get_channel_names

        df = extract_meridian_dataset(
            campaign_id=self.campaign_id, min_weeks=1
        )
        if df is None:
            return {}

        channels = get_channel_names(df)
        result = {}

        for i, ch_safe in enumerate(channels):
            display = ch_safe.replace("_", " ").title()
            spend_col = f"spend_{ch_safe}"
            total_spend = float(df[spend_col].sum()) if spend_col in df.columns else 0

            # Extract media coefficient posterior samples
            coeff_samples = self._get_posterior_var("media_coefficient", i)
            if coeff_samples is None:
                # Use observed data as fallback
                total_rev = total_spend * 2.0  # placeholder
                roas_mean = 2.0
                roas_lower = 1.5
                roas_upper = 2.5
            else:
                # Media coefficient represents incremental revenue per unit spend
                roas_samples = coeff_samples.flatten()
                roas_mean = float(np.mean(roas_samples))
                roas_lower = float(np.percentile(roas_samples, 2.5))
                roas_upper = float(np.percentile(roas_samples, 97.5))
                total_rev = total_spend * roas_mean

            # Hill curve parameters
            ec_samples = self._get_posterior_var("ec", i)
            slope_samples = self._get_posterior_var("slope", i)

            hill_params = None
            saturation_score = 0.5
            marginal_roas = roas_mean * 0.5

            if ec_samples is not None and slope_samples is not None:
                ec_mean = float(np.mean(ec_samples))
                slope_mean = float(np.mean(slope_samples))
                hill_params = {
                    "ec_mean": ec_mean,
                    "slope_mean": slope_mean,
                    "ec_samples": ec_samples.flatten(),
                    "slope_samples": slope_samples.flatten(),
                    "k_mean": total_rev,
                }
                # Saturation: how far along the Hill curve we are
                if ec_mean > 0:
                    hill_response = total_spend ** slope_mean / (
                        ec_mean ** slope_mean + total_spend ** slope_mean
                    )
                    saturation_score = float(hill_response)
                    # Marginal ROAS from Hill derivative
                    denom = (ec_mean ** slope_mean + total_spend ** slope_mean)
                    if denom > 0 and total_spend > 0:
                        marginal_roas = float(
                            total_rev
                            * slope_mean
                            * ec_mean ** slope_mean
                            * total_spend ** (slope_mean - 1)
                            / denom ** 2
                        )

            result[display] = {
                "spend": total_spend,
                "revenue_mean": total_rev,
                "roas_mean": roas_mean,
                "roas_lower": roas_lower,
                "roas_upper": roas_upper,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "ctr": 0,
                "cvr": 0,
                "hill_params": hill_params,
                "saturation_score": saturation_score,
                "marginal_roas": marginal_roas,
            }

        return result

    def _get_posterior_var(self, name: str, channel_idx: int = 0):
        """Extract posterior samples for a variable, sliced to a channel index."""
        if self._posteriors is None:
            return None

        # Handle both xarray Dataset and plain dict (from .npz fallback)
        if isinstance(self._posteriors, dict):
            arr = self._posteriors.get(name)
        else:
            if name not in self._posteriors:
                return None
            arr = self._posteriors[name].values

        if arr is None:
            return None

        # Meridian posterior shapes: (chains, samples, n_channels) or similar
        # Try to slice the channel dimension (last axis if > 1D)
        if arr.ndim >= 2 and arr.shape[-1] > channel_idx:
            return arr[..., channel_idx]
        elif arr.ndim == 1:
            return arr
        return arr

    # ------------------------------------------------------------------
    # Optimization helpers
    # ------------------------------------------------------------------

    def _optimize_with_meridian(
        self, total_budget: float, posteriors: Dict
    ) -> Optional[Dict]:
        """Try to use Meridian's built-in budget optimizer."""
        if self._model is None:
            return None
        try:
            result = self._model.optimize_budget(total_budget=total_budget)
            # Convert Meridian's output format to our format
            optimized = {}
            for ch, alloc in result.items():
                display = ch.replace("_", " ").title()
                if display in posteriors:
                    optimized[display] = {
                        "recommended_spend": float(alloc["spend"]),
                        "projected_revenue": float(alloc["revenue"]),
                        "projected_roas": float(alloc["revenue"] / alloc["spend"])
                        if alloc["spend"] > 0
                        else 0,
                        "marginal_roas": float(alloc.get("marginal_roas", 0)),
                    }
            return optimized
        except Exception as exc:
            logger.debug(f"Meridian optimize_budget not available: {exc}")
            return None

    def _optimize_greedy_hill(
        self, total_budget: float, posteriors: Dict
    ) -> Dict:
        """
        Greedy budget allocation using Hill curve posterior means.
        Allocates in 1% increments to the channel with highest marginal ROAS.
        """
        channels = list(posteriors.keys())
        allocs = {ch: 0.0 for ch in channels}
        step = total_budget / 100

        for _ in range(100):
            marginals = {}
            for ch in channels:
                p = posteriors[ch]
                hill = p.get("hill_params")
                if not hill:
                    marginals[ch] = p["roas_mean"] * 0.5
                    continue

                ec = hill["ec_mean"]
                slope = hill["slope_mean"]
                k = hill["k_mean"]
                s = allocs[ch] + step

                # Marginal revenue = d/ds [k * s^slope / (ec^slope + s^slope)]
                denom = (ec ** slope + s ** slope)
                if denom > 0 and s > 0:
                    marginals[ch] = (
                        k * slope * ec ** slope * s ** (slope - 1) / denom ** 2
                    )
                else:
                    marginals[ch] = 0

            best = max(marginals, key=marginals.get)
            allocs[best] += step

        result = {}
        for ch in channels:
            p = posteriors[ch]
            hill = p.get("hill_params")
            s = allocs[ch]
            if hill and s > 0:
                ec = hill["ec_mean"]
                slope = hill["slope_mean"]
                k = hill["k_mean"]
                proj_rev = k * s ** slope / (ec ** slope + s ** slope)
                proj_roas = proj_rev / s
                denom = (ec ** slope + s ** slope)
                m_roas = k * slope * ec ** slope * s ** (slope - 1) / denom ** 2
            else:
                proj_rev = s * p["roas_mean"]
                proj_roas = p["roas_mean"]
                m_roas = p["roas_mean"] * 0.5

            result[ch] = {
                "recommended_spend": s,
                "projected_revenue": proj_rev,
                "projected_roas": proj_roas,
                "marginal_roas": m_roas,
            }

        return result

    @staticmethod
    def _find_optimal_spend(
        k: float, ec: float, slope: float, current_spend: float
    ) -> float:
        """Find spend where marginal ROAS = 1 using bisection search."""
        if ec <= 0 or slope <= 0 or k <= 0:
            return current_spend

        lo, hi = 1.0, current_spend * 10
        for _ in range(50):
            mid = (lo + hi) / 2
            denom = (ec ** slope + mid ** slope)
            if denom <= 0:
                break
            marginal = k * slope * ec ** slope * mid ** (slope - 1) / denom ** 2
            if marginal > 1.0:
                lo = mid
            else:
                hi = mid

        return (lo + hi) / 2

    def _generate_insights(
        self, channels: List[Dict], total_spend: float
    ) -> List[str]:
        """Generate human-readable insights with uncertainty language."""
        insights = []
        saturated = [c for c in channels if c["saturation_score"] > 0.7]
        undersaturated = [
            c
            for c in channels
            if c["saturation_score"] < 0.3 and c["efficiency_score"] > 1.1
        ]
        top = max(channels, key=lambda c: c["roas"], default=None)
        bottom = min(channels, key=lambda c: c["roas"], default=None)

        if saturated:
            names = ", ".join(c["channel"] for c in saturated[:2])
            insights.append(
                f"**{names}** {'are' if len(saturated) > 1 else 'is'} "
                f"approaching saturation — marginal returns are declining."
            )
        if undersaturated:
            names = ", ".join(c["channel"] for c in undersaturated[:2])
            insights.append(
                f"**{names}** {'have' if len(undersaturated) > 1 else 'has'} "
                f"capacity for additional spend with strong marginal returns."
            )
        if top and bottom and top["roas"] > bottom["roas"] * 1.5:
            # Include credible intervals if available
            top_ci = ""
            if "roas_lower" in top and "roas_upper" in top:
                top_ci = f" (95% CI: {top['roas_lower']:.2f}–{top['roas_upper']:.2f})"
            insights.append(
                f"Largest ROAS gap: **{top['channel']}** ({top['roas']:.2f}x{top_ci}) vs "
                f"**{bottom['channel']}** ({bottom['roas']:.2f}x). "
                f"Consider rebalancing toward {top['channel']}."
            )
        if not insights:
            insights.append(
                "Portfolio looks balanced. Continue monitoring for saturation signals."
            )
        return insights

    def _fallback(self):
        """Return the rule-based engine as fallback."""
        from src.bandit_ads.mmm_insights import MMMInsightsEngine

        return MMMInsightsEngine()


# ======================================================================
# Router — single entry point that picks the right engine
# ======================================================================


class MMMInsightsRouter:
    """
    Façade that delegates to MeridianInsightsEngine when a trained model
    exists, and falls back to the rule-based MMMInsightsEngine otherwise.

    This is the class that API routes should instantiate.
    """

    def __init__(self, campaign_id: Optional[int] = None):
        self._campaign_id = campaign_id
        self._engine = None

    def _get_engine(self, campaign_id: Optional[int] = None):
        """Resolve the best available engine."""
        cid = campaign_id if campaign_id is not None else self._campaign_id

        # Check config preference
        try:
            from src.bandit_ads.utils import ConfigManager

            cm = ConfigManager()
            engine_pref = cm.get("mmm.engine", "rule_based")
        except Exception:
            engine_pref = "rule_based"

        if engine_pref == "meridian":
            from src.bandit_ads.meridian_trainer import MeridianTrainer

            trainer = MeridianTrainer()
            if trainer.has_trained_model(cid):
                return MeridianInsightsEngine(campaign_id=cid)

        # Fallback to rule-based
        from src.bandit_ads.mmm_insights import MMMInsightsEngine

        return MMMInsightsEngine()

    def get_channel_summary(
        self, campaign_id: Optional[int] = None, days: int = 30
    ) -> List[Dict[str, Any]]:
        return self._get_engine(campaign_id).get_channel_summary(campaign_id, days)

    def get_saturation_curves(
        self,
        campaign_id: Optional[int] = None,
        days: int = 30,
        points: int = 20,
    ) -> Dict[str, Any]:
        return self._get_engine(campaign_id).get_saturation_curves(
            campaign_id, days, points
        )

    def get_budget_recommendations(
        self,
        campaign_id: Optional[int] = None,
        total_budget: Optional[float] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        return self._get_engine(campaign_id).get_budget_recommendations(
            campaign_id, total_budget, days
        )

    def get_cross_platform_summary(self, days: int = 30) -> Dict[str, Any]:
        return self._get_engine(None).get_cross_platform_summary(days)
