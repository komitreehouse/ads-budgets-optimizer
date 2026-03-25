"""
Meridian Data Preparation

Transforms IPSA's Metric/Arm database tables into the format expected by
Google Meridian's InputData.  Also provides helpers for data-sufficiency
validation and for converting incrementality experiment results into
Meridian-compatible informative priors.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.bandit_ads.utils import get_logger

logger = get_logger("meridian_data")

# Minimum data requirements for Meridian training
MIN_TRAINING_WEEKS = 12
MIN_NONZERO_CHANNELS = 2


def extract_meridian_dataset(
    campaign_id: Optional[int] = None,
    min_weeks: int = MIN_TRAINING_WEEKS,
) -> Optional[pd.DataFrame]:
    """
    Query Metric+Arm tables and return a weekly-aggregated wide DataFrame
    suitable for Meridian training.

    Columns produced:
        date          — Monday of each ISO week (datetime)
        revenue       — total revenue across all channels that week (KPI)
        spend_<ch>    — spend for channel <ch>
        impressions_<ch> — impressions for channel <ch>

    Returns None if data is insufficient.
    """
    try:
        from src.bandit_ads.database import Metric, Arm, get_db_manager

        db_manager = get_db_manager()
    except Exception as exc:
        logger.warning(f"Cannot access database: {exc}")
        return None

    with db_manager.get_session() as session:
        q = session.query(Metric, Arm).join(Arm, Metric.arm_id == Arm.id)
        if campaign_id is not None:
            q = q.filter(Arm.campaign_id == campaign_id)

        rows = []
        for metric, arm in q.all():
            # Combine platform + channel to match MMM convention
            # e.g., platform="Google", channel="Search" → "Google Search"
            channel = f"{arm.platform} {arm.channel}" if arm.platform and arm.channel else (arm.channel or arm.platform or "Unknown")
            rows.append(
                {
                    "date": metric.timestamp,
                    "channel": channel,
                    "spend": float(metric.cost or 0),
                    "revenue": float(metric.revenue or 0),
                    "impressions": int(metric.impressions or 0),
                }
            )

    if not rows:
        logger.info("No metric rows found — cannot build Meridian dataset")
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])

    # Aggregate to ISO-week level (Monday start)
    df["week"] = df["date"].dt.to_period("W-MON").dt.start_time

    weekly = (
        df.groupby(["week", "channel"])
        .agg(spend=("spend", "sum"), revenue=("revenue", "sum"), impressions=("impressions", "sum"))
        .reset_index()
    )

    # Pivot to wide format
    channels = sorted(weekly["channel"].unique())
    pivot_parts = [weekly.groupby("week")["revenue"].sum().rename("revenue")]

    for ch in channels:
        ch_data = weekly[weekly["channel"] == ch].set_index("week")
        safe_name = _safe_column_name(ch)
        pivot_parts.append(ch_data["spend"].rename(f"spend_{safe_name}"))
        pivot_parts.append(ch_data["impressions"].rename(f"impressions_{safe_name}"))

    wide = pd.concat(pivot_parts, axis=1).fillna(0).reset_index()
    wide = wide.rename(columns={"week": "date"})
    wide = wide.sort_values("date").reset_index(drop=True)

    # Validate sufficiency
    ok, reason = validate_data_sufficiency(wide, min_weeks=min_weeks)
    if not ok:
        logger.info(f"Data insufficient for Meridian: {reason}")
        return None

    logger.info(
        f"Meridian dataset ready: {len(wide)} weeks, "
        f"{len(channels)} channels ({', '.join(channels)})"
    )
    return wide


def validate_data_sufficiency(
    df: pd.DataFrame,
    min_weeks: int = MIN_TRAINING_WEEKS,
) -> Tuple[bool, str]:
    """
    Check whether a wide-format DataFrame has enough data for Meridian.

    Returns (ok, reason).
    """
    if df is None or df.empty:
        return False, "DataFrame is empty"

    n_weeks = len(df)
    if n_weeks < min_weeks:
        return False, f"Only {n_weeks} weeks of data; need at least {min_weeks}"

    # Check that we have at least MIN_NONZERO_CHANNELS with meaningful spend
    spend_cols = [c for c in df.columns if c.startswith("spend_")]
    nonzero = sum(1 for c in spend_cols if df[c].sum() > 0)
    if nonzero < MIN_NONZERO_CHANNELS:
        return False, f"Only {nonzero} channels with spend; need at least {MIN_NONZERO_CHANNELS}"

    # Check KPI column has variation
    if df["revenue"].std() == 0:
        return False, "Revenue has zero variance — nothing to model"

    return True, "ok"


def get_channel_names(df: pd.DataFrame) -> List[str]:
    """Extract channel names from the wide DataFrame column names."""
    channels = []
    for col in df.columns:
        if col.startswith("spend_"):
            channels.append(col[len("spend_"):])
    return channels


def build_meridian_input_data(df: pd.DataFrame) -> Any:
    """
    Convert the wide DataFrame into a Meridian InputData object.

    This is the final step before training — it wraps the DataFrame in
    Meridian's expected container with proper column mapping.
    """
    try:
        from meridian.data import input_data as meridian_input
    except ImportError:
        logger.error(
            "google-meridian is not installed. "
            "Install with: pip install google-meridian"
        )
        raise

    channels = get_channel_names(df)
    spend_cols = [f"spend_{ch}" for ch in channels]
    media_names = [_display_name(ch) for ch in channels]

    # Meridian expects numpy arrays with shape (n_geos, n_times, n_channels)
    # For national-level (single geo), n_geos=1
    n_times = len(df)
    n_channels = len(channels)

    media_spend = df[spend_cols].values.reshape(1, n_times, n_channels)
    revenue = df["revenue"].values.reshape(1, n_times)

    # Impressions (optional reach proxy)
    imp_cols = [f"impressions_{ch}" for ch in channels]
    has_impressions = all(c in df.columns for c in imp_cols)
    media_impressions = (
        df[imp_cols].values.reshape(1, n_times, n_channels)
        if has_impressions
        else None
    )

    input_data = meridian_input.InputData(
        media_spend=media_spend,
        media_names=media_names,
        revenue=revenue,
        date_strs=df["date"].dt.strftime("%Y-%m-%d").tolist(),
        media_impressions=media_impressions,
    )

    return input_data


def prepare_prior_config(
    incrementality_results: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Convert incrementality experiment results into Meridian-compatible
    informative priors on media coefficients.

    Each incrementality result should contain:
        - channel: str
        - incremental_roas: float
        - confidence_interval: (lower, upper)

    Returns a dict suitable for passing to MeridianTrainer.
    """
    priors: Dict[str, Any] = {}
    if not incrementality_results:
        return priors

    for result in incrementality_results:
        channel = result.get("channel")
        iroas = result.get("incremental_roas")
        ci = result.get("confidence_interval")
        if channel is None or iroas is None:
            continue

        safe = _safe_column_name(channel)

        # Convert CI to std dev (assume normal approximation)
        if ci and len(ci) == 2:
            std = (ci[1] - ci[0]) / (2 * 1.96)  # 95% CI → 1 std
        else:
            std = iroas * 0.25  # fallback: 25% CV

        priors[safe] = {
            "mean": float(iroas),
            "std": float(max(std, 0.01)),
            "source": "incrementality_experiment",
        }
        logger.info(
            f"Meridian prior for {channel}: mean={iroas:.3f}, std={std:.3f}"
        )

    return priors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_column_name(name: str) -> str:
    """Convert a channel name to a safe column suffix."""
    return name.strip().lower().replace(" ", "_").replace("/", "_")


def _display_name(safe: str) -> str:
    """Convert a safe column name back to display form."""
    return safe.replace("_", " ").title()
