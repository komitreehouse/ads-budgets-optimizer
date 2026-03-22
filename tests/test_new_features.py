"""
Tests for new features: Export, Attribution, Forecasting, Scenario Planning.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExportService:
    def setup_method(self):
        from src.bandit_ads.export import ExportService
        self.svc = ExportService()

    def test_metrics_csv_returns_bytes(self):
        data = self.svc.metrics_csv(999, days=30)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_metrics_csv_has_header(self):
        data = self.svc.metrics_csv(999, days=30)
        text = data.decode()
        assert "date" in text
        assert "channel" in text
        assert "spend" in text
        assert "roas" in text

    def test_allocation_csv_returns_bytes(self):
        data = self.svc.allocation_csv(999)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_allocation_csv_has_header(self):
        data = self.svc.allocation_csv(999)
        text = data.decode()
        assert "arm" in text
        assert "platform" in text
        assert "allocation_pct" in text

    def test_decisions_csv_returns_bytes(self):
        data = self.svc.decisions_csv(999, days=30)
        assert isinstance(data, bytes)

    def test_decisions_csv_has_header(self):
        data = self.svc.decisions_csv(None, days=30)
        text = data.decode()
        assert "timestamp" in text
        assert "campaign_id" in text

    def test_pdf_returns_valid_pdf(self):
        data = self.svc.campaign_pdf(999, campaign_name="Test Campaign")
        assert isinstance(data, bytes)
        assert data[:4] == b"%PDF"

    def test_stub_metrics_shape(self):
        rows = self.svc._stub_metrics()
        assert len(rows) == 60  # 30 days × 2 channels
        first = rows[0]
        assert "date" in first
        assert "spend" in first
        assert "revenue" in first
        assert first["roas"] == pytest.approx(first["revenue"] / first["spend"], rel=1e-3)

    def test_stub_allocation_shape(self):
        rows = self.svc._stub_allocation()
        assert len(rows) == 3
        total_alloc = sum(r["allocation_pct"] for r in rows)
        assert total_alloc == pytest.approx(1.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

class TestAttributionEngine:
    def setup_method(self):
        from src.bandit_ads.attribution import AttributionEngine
        self.engine = AttributionEngine()

    def test_linear_shares_sum_to_100(self):
        result = self.engine.calculate(999, method="linear")
        total = sum(v["share_pct"] for v in result.values())
        assert total == pytest.approx(100.0, rel=0.01)

    def test_time_decay_shares_sum_to_100(self):
        result = self.engine.calculate(999, method="time_decay")
        total = sum(v["share_pct"] for v in result.values())
        assert total == pytest.approx(100.0, rel=0.01)

    def test_last_touch_shares_sum_to_100(self):
        result = self.engine.calculate(999, method="last_touch")
        total = sum(v["share_pct"] for v in result.values())
        assert total == pytest.approx(100.0, rel=0.01)

    def test_stub_has_expected_channels(self):
        result = self.engine._stub("linear")
        assert "Google Search" in result
        assert "Meta Social" in result
        assert "Programmatic" in result

    def test_roas_computed_correctly(self):
        result = self.engine.calculate(999, method="linear")
        for ch, vals in result.items():
            if vals["spend"] > 0:
                expected_roas = vals["attributed_revenue"] / vals["spend"]
                assert vals["roas"] == pytest.approx(expected_roas, rel=0.01)

    def test_all_methods_return_same_channels(self):
        channels_linear = set(self.engine.calculate(999, method="linear").keys())
        channels_decay = set(self.engine.calculate(999, method="time_decay").keys())
        channels_last = set(self.engine.calculate(999, method="last_touch").keys())
        assert channels_linear == channels_decay == channels_last


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------

class TestROIForecaster:
    def setup_method(self):
        from src.bandit_ads.forecasting import ROIForecaster
        self.forecaster = ROIForecaster()

    def test_forecast_returns_dict(self):
        result = self.forecaster.forecast(999, horizon_days=7)
        assert isinstance(result, dict)

    def test_forecast_has_channels(self):
        result = self.forecaster.forecast(999, horizon_days=7)
        assert "channels" in result

    def test_forecast_date_length_matches_horizon(self):
        result = self.forecaster.forecast(999, horizon_days=7)
        for ch_data in result["channels"].values():
            assert len(ch_data["dates"]) == 7
            assert len(ch_data["roas_mean"]) == 7
            assert len(ch_data["roas_lower"]) == 7
            assert len(ch_data["roas_upper"]) == 7

    def test_confidence_bounds_ordered(self):
        result = self.forecaster.forecast(999, horizon_days=14)
        for ch_data in result["channels"].values():
            for lo, mid, hi in zip(ch_data["roas_lower"], ch_data["roas_mean"], ch_data["roas_upper"]):
                assert lo <= mid <= hi

    def test_positive_roas_projections(self):
        result = self.forecaster.forecast(999, horizon_days=7)
        for ch_data in result["channels"].values():
            assert all(v >= 0 for v in ch_data["roas_mean"])


# ---------------------------------------------------------------------------
# Scenario Planning
# ---------------------------------------------------------------------------

class TestScenarioPlanner:
    def setup_method(self):
        from src.bandit_ads.scenario_planner import ScenarioPlanner
        self.planner = ScenarioPlanner()

    def test_simulate_returns_current_and_proposed(self):
        result = self.planner.simulate(999, budget_changes={"Google Search": 5000}, horizon_days=7)
        assert "current" in result
        assert "proposed" in result
        assert "delta" in result

    def test_current_plan_has_required_keys(self):
        result = self.planner.simulate(999, budget_changes={}, horizon_days=7)
        current = result["current"]
        assert "total_spend" in current
        assert "total_revenue" in current
        assert "blended_roas" in current

    def test_budget_increase_raises_spend(self):
        result = self.planner.simulate(
            999,
            budget_changes={"Google Search": 10000},
            horizon_days=7
        )
        assert result["proposed"]["total_spend"] >= result["current"]["total_spend"]

    def test_delta_revenue_sign(self):
        result = self.planner.simulate(
            999,
            budget_changes={"Google Search": 5000},
            horizon_days=7
        )
        # If proposed spend is higher, revenue should be >= current
        if result["proposed"]["total_spend"] > result["current"]["total_spend"]:
            assert result["delta"]["total_revenue"] >= 0


# ---------------------------------------------------------------------------
# API routes (integration-style, no server needed)
# ---------------------------------------------------------------------------

class TestExportAPIRoutes:
    """Test export route logic without starting a server."""

    def test_csv_metrics_route_bytes(self):
        import asyncio
        from src.bandit_ads.api.routes.export import export_csv
        resp = asyncio.get_event_loop().run_until_complete(
            export_csv(campaign_id=999, type="metrics", days=30)
        )
        assert resp.media_type == "text/csv"
        assert b"date" in resp.body

    def test_csv_allocation_route_bytes(self):
        import asyncio
        from src.bandit_ads.api.routes.export import export_csv
        resp = asyncio.get_event_loop().run_until_complete(
            export_csv(campaign_id=999, type="allocation", days=30)
        )
        assert resp.media_type == "text/csv"
        assert b"arm" in resp.body

    def test_csv_invalid_type_raises_400(self):
        import asyncio
        from fastapi import HTTPException
        from src.bandit_ads.api.routes.export import export_csv
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                export_csv(campaign_id=999, type="invalid", days=30)
            )
        assert exc_info.value.status_code == 400

    def test_pdf_route_returns_pdf_bytes(self):
        import asyncio
        from src.bandit_ads.api.routes.export import export_pdf
        resp = asyncio.get_event_loop().run_until_complete(
            export_pdf(campaign_id=999, campaign_name="Test")
        )
        assert resp.media_type == "application/pdf"
        assert resp.body[:4] == b"%PDF"


class TestAttributionAPIRoute:
    def test_attribution_route_linear(self):
        import asyncio
        from src.bandit_ads.api.routes.attribution import get_attribution
        result = asyncio.get_event_loop().run_until_complete(
            get_attribution(campaign_id=999, method="linear", days=30)
        )
        assert result["method"] == "linear"
        assert "channels" in result
        total = sum(v["share_pct"] for v in result["channels"].values())
        assert total == pytest.approx(100.0, rel=0.01)
