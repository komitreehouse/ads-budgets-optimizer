"""
Tests for the Meridian integration pipeline.

Validates the data extraction, sufficiency checks, router fallback,
bridge conversion, and trainer status — all without requiring
google-meridian to be installed.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Data extraction & validation
# ---------------------------------------------------------------------------


class TestDataExtraction:
    """Test meridian_data.py functions."""

    def test_extract_meridian_dataset_returns_dataframe(self):
        """extract_meridian_dataset should return a wide DataFrame with 12+ weeks."""
        from src.bandit_ads.meridian_data import extract_meridian_dataset

        df = extract_meridian_dataset(min_weeks=12)
        assert df is not None, "Expected a DataFrame but got None — is sample data loaded?"
        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 12, f"Expected >= 12 weeks, got {len(df)}"

    def test_dataset_has_required_columns(self):
        """Dataset must have date, revenue, and at least 2 spend_ columns."""
        from src.bandit_ads.meridian_data import extract_meridian_dataset

        df = extract_meridian_dataset(min_weeks=12)
        assert df is not None
        assert "date" in df.columns
        assert "revenue" in df.columns

        spend_cols = [c for c in df.columns if c.startswith("spend_")]
        assert len(spend_cols) >= 2, f"Expected >= 2 spend columns, got {spend_cols}"

    def test_dataset_channels_match_db(self):
        """Channels in the dataset should combine platform + channel (e.g. 'google_search')."""
        from src.bandit_ads.meridian_data import extract_meridian_dataset, get_channel_names

        df = extract_meridian_dataset(min_weeks=12)
        assert df is not None
        channels = get_channel_names(df)
        # Our sample data has Google Search, Meta Social, Google Display, etc.
        assert any("google" in ch for ch in channels), f"Expected a Google channel, got {channels}"
        assert any("meta" in ch for ch in channels), f"Expected a Meta channel, got {channels}"

    def test_dataset_no_negative_values(self):
        """Spend and revenue should never be negative."""
        from src.bandit_ads.meridian_data import extract_meridian_dataset

        df = extract_meridian_dataset(min_weeks=12)
        assert df is not None
        spend_cols = [c for c in df.columns if c.startswith("spend_")]
        for col in spend_cols + ["revenue"]:
            assert (df[col] >= 0).all(), f"Negative values in {col}"


class TestDataSufficiency:
    """Test validate_data_sufficiency."""

    def test_sufficient_data_passes(self):
        from src.bandit_ads.meridian_data import extract_meridian_dataset, validate_data_sufficiency

        df = extract_meridian_dataset(min_weeks=1)  # low threshold to get any data
        if df is not None:
            ok, reason = validate_data_sufficiency(df, min_weeks=12)
            # Our sample data has 26 weeks, so this should pass
            assert ok, f"Expected sufficient data but got: {reason}"

    def test_insufficient_weeks_fails(self):
        from src.bandit_ads.meridian_data import validate_data_sufficiency

        # Create a tiny DataFrame with only 5 weeks
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=5, freq="W"),
            "revenue": [100] * 5,
            "spend_google_search": [50] * 5,
            "spend_meta_social": [30] * 5,
        })
        ok, reason = validate_data_sufficiency(df, min_weeks=12)
        assert not ok
        assert "5 weeks" in reason

    def test_zero_spend_channels_fails(self):
        from src.bandit_ads.meridian_data import validate_data_sufficiency

        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=15, freq="W"),
            "revenue": [100] * 15,
            "spend_google_search": [50] * 15,
            "spend_meta_social": [0] * 15,  # all zero
        })
        ok, reason = validate_data_sufficiency(df, min_weeks=12)
        assert not ok
        assert "1 channels" in reason

    def test_empty_dataframe_fails(self):
        from src.bandit_ads.meridian_data import validate_data_sufficiency

        ok, reason = validate_data_sufficiency(pd.DataFrame(), min_weeks=12)
        assert not ok

    def test_none_fails(self):
        from src.bandit_ads.meridian_data import validate_data_sufficiency

        ok, reason = validate_data_sufficiency(None, min_weeks=12)
        assert not ok


# ---------------------------------------------------------------------------
# Router fallback
# ---------------------------------------------------------------------------


class TestMMMInsightsRouter:
    """Test that the router falls back to rule-based when no Meridian model exists."""

    def test_router_returns_results(self):
        from src.bandit_ads.meridian_insights import MMMInsightsRouter

        router = MMMInsightsRouter()
        result = router.get_cross_platform_summary(days=200)
        assert "channels" in result
        assert "blended_roas" in result
        assert len(result["channels"]) > 0

    def test_router_returns_live_data(self):
        """Router should return real DB data, not stubs (since we have sample data)."""
        from src.bandit_ads.meridian_insights import MMMInsightsRouter

        router = MMMInsightsRouter()
        result = router.get_cross_platform_summary(days=200)
        channels = result["channels"]

        # Live data has combined platform+channel names like "Google Search"
        channel_names = [c["channel"] for c in channels]
        assert any("Google" in n for n in channel_names), (
            f"Expected 'Google ...' channel from live data, got {channel_names}"
        )

    def test_router_channel_summary(self):
        from src.bandit_ads.meridian_insights import MMMInsightsRouter

        router = MMMInsightsRouter()
        channels = router.get_channel_summary(campaign_id=1, days=200)
        assert len(channels) > 0
        for ch in channels:
            assert "channel" in ch
            assert "roas" in ch
            assert "saturation_score" in ch

    def test_router_saturation_curves(self):
        from src.bandit_ads.meridian_insights import MMMInsightsRouter

        router = MMMInsightsRouter()
        curves = router.get_saturation_curves(campaign_id=1, days=200)
        assert len(curves) > 0
        for ch, data in curves.items():
            assert "spend_points" in data
            assert "roas_points" in data
            assert "optimal_spend" in data
            assert len(data["spend_points"]) > 0

    def test_router_budget_recommendations(self):
        from src.bandit_ads.meridian_insights import MMMInsightsRouter

        router = MMMInsightsRouter()
        recs = router.get_budget_recommendations(campaign_id=1, days=200)
        assert "channels" in recs
        assert "roas_uplift_pct" in recs
        assert len(recs["channels"]) > 0


# ---------------------------------------------------------------------------
# Bridge conversion
# ---------------------------------------------------------------------------


class TestBridgeConversion:
    """Test meridian_bridge.py posterior → Beta prior conversion."""

    def test_posteriors_to_beta_priors(self):
        from src.bandit_ads.meridian_bridge import posteriors_to_beta_priors

        posteriors = {
            "Google Search": {"roas_mean": 2.5, "roas_lower": 2.1, "roas_upper": 2.9},
            "Meta Social": {"roas_mean": 1.8, "roas_lower": 1.3, "roas_upper": 2.3},
        }
        priors = posteriors_to_beta_priors(posteriors)

        assert "Google Search" in priors
        assert "Meta Social" in priors

        for ch, p in priors.items():
            assert p["alpha"] >= 1.0, f"{ch}: alpha={p['alpha']} should be >= 1"
            assert p["beta"] >= 1.0, f"{ch}: beta={p['beta']} should be >= 1"
            assert p["source"] == "meridian"

    def test_higher_roas_gives_higher_alpha_ratio(self):
        """Channel with higher ROAS should have higher alpha/(alpha+beta) ratio."""
        from src.bandit_ads.meridian_bridge import posteriors_to_beta_priors

        posteriors = {
            "High": {"roas_mean": 5.0, "roas_lower": 4.0, "roas_upper": 6.0},
            "Low": {"roas_mean": 0.5, "roas_lower": 0.3, "roas_upper": 0.7},
        }
        priors = posteriors_to_beta_priors(posteriors)

        high_ratio = priors["High"]["alpha"] / (priors["High"]["alpha"] + priors["High"]["beta"])
        low_ratio = priors["Low"]["alpha"] / (priors["Low"]["alpha"] + priors["Low"]["beta"])
        assert high_ratio > low_ratio

    def test_tighter_ci_gives_higher_concentration(self):
        """Tighter CI should give higher total alpha+beta (more confident prior)."""
        from src.bandit_ads.meridian_bridge import posteriors_to_beta_priors

        tight = {"roas_mean": 2.0, "roas_lower": 1.9, "roas_upper": 2.1}
        wide = {"roas_mean": 2.0, "roas_lower": 1.0, "roas_upper": 3.0}

        priors = posteriors_to_beta_priors({"Tight": tight, "Wide": wide})
        tight_total = priors["Tight"]["alpha"] + priors["Tight"]["beta"]
        wide_total = priors["Wide"]["alpha"] + priors["Wide"]["beta"]
        assert tight_total > wide_total, "Tighter CI should give more concentrated prior"


# ---------------------------------------------------------------------------
# Trainer status (without actual training)
# ---------------------------------------------------------------------------


class TestTrainerStatus:
    """Test MeridianTrainer status checks without running MCMC."""

    def test_no_trained_model(self):
        from src.bandit_ads.meridian_trainer import MeridianTrainer

        trainer = MeridianTrainer()
        assert not trainer.has_trained_model()
        assert not trainer.has_trained_model(campaign_id=1)

    def test_training_status_not_trained(self):
        from src.bandit_ads.meridian_trainer import MeridianTrainer

        trainer = MeridianTrainer()
        status = trainer.get_training_status()
        assert status["trained"] is False

    def test_convergence_diagnostics_empty(self):
        from src.bandit_ads.meridian_trainer import MeridianTrainer

        trainer = MeridianTrainer()
        diag = trainer.get_convergence_diagnostics()
        assert diag == {}


# ---------------------------------------------------------------------------
# Prior config from incrementality
# ---------------------------------------------------------------------------


class TestPriorConfig:
    """Test prepare_prior_config conversion."""

    def test_converts_incrementality_results(self):
        from src.bandit_ads.meridian_data import prepare_prior_config

        results = [
            {
                "channel": "Google Search",
                "incremental_roas": 2.1,
                "confidence_interval": (1.8, 2.4),
            },
            {
                "channel": "Meta Social",
                "incremental_roas": 1.5,
                "confidence_interval": (1.0, 2.0),
            },
        ]
        priors = prepare_prior_config(results)

        assert "google_search" in priors
        assert "meta_social" in priors
        assert priors["google_search"]["mean"] == 2.1
        assert priors["google_search"]["std"] > 0
        assert priors["google_search"]["source"] == "incrementality_experiment"

    def test_empty_results_returns_empty(self):
        from src.bandit_ads.meridian_data import prepare_prior_config

        assert prepare_prior_config(None) == {}
        assert prepare_prior_config([]) == {}

    def test_missing_fields_skipped(self):
        from src.bandit_ads.meridian_data import prepare_prior_config

        results = [{"channel": "Test"}]  # missing incremental_roas
        assert prepare_prior_config(results) == {}
