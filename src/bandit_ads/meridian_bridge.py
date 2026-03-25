"""
Meridian ↔ Bandit Bridge

Converts between Meridian posterior distributions and Thompson Sampling Beta
priors, closing the loop:

    incrementality experiments → Meridian informative priors
    Meridian posteriors        → bandit Beta(alpha, beta)
    bandit allocations         → new data → Meridian re-training
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.bandit_ads.utils import get_logger

logger = get_logger("meridian_bridge")


def posteriors_to_beta_priors(
    channel_posteriors: Dict[str, Dict],
) -> Dict[str, Dict[str, float]]:
    """
    Convert Meridian media-coefficient posteriors to Beta(alpha, beta) params
    suitable for Thompson Sampling.

    Each entry in *channel_posteriors* should contain:
        roas_mean   — posterior mean of the ROAS / media coefficient
        roas_lower  — 2.5th percentile
        roas_upper  — 97.5th percentile

    The conversion:
    1. Map ROAS to a [0, 1] "success rate" via sigmoid: p = roas / (1 + roas)
    2. Estimate variance from the credible interval
    3. Fit Beta(alpha, beta) using method of moments

    Returns {channel: {"alpha": float, "beta": float, "source": "meridian"}}.
    """
    priors: Dict[str, Dict[str, float]] = {}

    for channel, post in channel_posteriors.items():
        roas_mean = post.get("roas_mean", 1.0)
        roas_lower = post.get("roas_lower", roas_mean * 0.7)
        roas_upper = post.get("roas_upper", roas_mean * 1.3)

        # Step 1: sigmoid transform to [0,1]
        p_mean = _sigmoid(roas_mean)
        p_lower = _sigmoid(roas_lower)
        p_upper = _sigmoid(roas_upper)

        # Step 2: estimate variance from CI width
        # 95% CI spans ~4 std devs in sigmoid space
        p_std = max((p_upper - p_lower) / (2 * 1.96), 1e-4)
        p_var = p_std ** 2

        # Clamp to valid Beta range
        p_mean = np.clip(p_mean, 0.01, 0.99)
        if p_var >= p_mean * (1 - p_mean):
            p_var = p_mean * (1 - p_mean) * 0.9

        # Step 3: method of moments for Beta
        alpha, beta = _moments_to_beta(p_mean, p_var)

        priors[channel] = {
            "alpha": round(float(alpha), 3),
            "beta": round(float(beta), 3),
            "roas_mean": round(roas_mean, 4),
            "source": "meridian",
        }
        logger.debug(
            f"Meridian → Beta prior for {channel}: "
            f"α={alpha:.2f}, β={beta:.2f} (ROAS={roas_mean:.2f})"
        )

    return priors


def incrementality_to_meridian_priors(
    experiment_results: List[Dict],
) -> Dict[str, Dict[str, Any]]:
    """
    Convert incrementality experiment results into Meridian-compatible
    informative priors.

    This is a thin wrapper around meridian_data.prepare_prior_config,
    provided here for symmetry and to keep the bridge module as the
    single point of integration.

    Each result dict should have:
        channel, incremental_roas, confidence_interval (lower, upper)
    """
    from src.bandit_ads.meridian_data import prepare_prior_config

    return prepare_prior_config(experiment_results)


def extract_channel_posteriors(
    campaign_id: Optional[int] = None,
) -> Dict[str, Dict]:
    """
    Load a trained Meridian model and extract per-channel posterior
    summaries (ROAS mean, CI, Hill params).

    Returns the same format expected by posteriors_to_beta_priors().
    """
    from src.bandit_ads.meridian_insights import MeridianInsightsEngine

    engine = MeridianInsightsEngine(campaign_id=campaign_id)
    if not engine._ensure_model():
        return {}

    return engine._extract_channel_posteriors()


def update_bandit_from_meridian(
    bandit: Any,
    campaign_id: Optional[int] = None,
) -> int:
    """
    End-to-end: load Meridian posteriors and push them into a
    Thompson Sampling bandit's alpha/beta parameters.

    Returns the number of arms updated.
    """
    posteriors = extract_channel_posteriors(campaign_id)
    if not posteriors:
        logger.info("No Meridian posteriors available — bandit unchanged")
        return 0

    beta_priors = posteriors_to_beta_priors(posteriors)
    updated = 0

    for arm in bandit.arms:
        arm_key = str(arm)
        # Match arm to channel by checking if channel name appears in arm key
        for channel, prior in beta_priors.items():
            if channel.lower() in arm_key.lower():
                bandit.alpha[arm_key] = prior["alpha"]
                bandit.beta[arm_key] = prior["beta"]
                updated += 1
                logger.info(
                    f"Updated bandit prior for {arm_key}: "
                    f"α={prior['alpha']}, β={prior['beta']} (from Meridian)"
                )
                break

    if updated > 0:
        # Force budget reallocation with new priors
        bandit.current_allocation = bandit._allocate_budget()

    return updated


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    """Map ROAS (0, ∞) to (0, 1) success probability."""
    return x / (1.0 + x) if x >= 0 else 0.0


def _moments_to_beta(
    mean: float, var: float
) -> Tuple[float, float]:
    """
    Method-of-moments estimation for Beta(alpha, beta).

    alpha = mean * (mean*(1-mean)/var - 1)
    beta  = (1-mean) * (mean*(1-mean)/var - 1)
    """
    temp = mean * (1 - mean) / var - 1
    alpha = max(1.0, mean * temp)
    beta = max(1.0, (1 - mean) * temp)
    return alpha, beta
