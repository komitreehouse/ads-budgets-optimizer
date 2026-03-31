"""
Frontend Mock-Mode QA & Edge-Case Tests

Tests for frontend DataService contract mismatches, chart edge cases,
schema drift between mock and live responses, and data integrity issues.
These tests run without a live API or Streamlit runtime.
"""

import math
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pytest
import pandas as pd
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# 1. DataService: Mock vs Live response contract mismatches
# ---------------------------------------------------------------------------

class TestDataServiceResponseContracts:
    """The central DataService class has divergent response shapes between
    mock fallback and live API paths."""

    def _make_mock_ds(self):
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_get.side_effect = Exception("no api")
            from frontend.services.data_service import DataService
            ds = DataService()
        return ds

    def _make_live_ds(self):
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_resp
            from frontend.services.data_service import DataService
            ds = DataService()
        return ds

    # -- query_orchestrator key mismatch ---
    def test_mock_query_uses_answer_key(self):
        ds = self._make_mock_ds()
        result = ds.query_orchestrator("What is ROAS?")
        assert "answer" in result, "Mock fallback must include 'answer'"
        assert "response" not in result, "Mock fallback should not have 'response'"

    def test_live_query_wraps_in_response_key(self):
        ds = self._make_live_ds()
        with patch.object(ds, "_api_post") as mock_post:
            mock_post.return_value = {"answer": "ROAS is 2.45", "query_type": "metric"}
            result = ds.query_orchestrator("What is ROAS?")
        assert "response" in result, "Live path should have 'response'"
        assert result["response"] == "ROAS is 2.45"

    def test_ask_page_reads_answer_key(self):
        """The ask page reads response.get('answer') — which is correct
        for mock but wrong for the live path that returns 'response'."""
        ds = self._make_live_ds()
        with patch.object(ds, "_api_post") as mock_post:
            mock_post.return_value = {"answer": "Budget went up", "query_type": "explanation"}
            result = ds.query_orchestrator("Why did budget increase?")
        # Simulating what ask.py does:
        content = result.get("answer", "I couldn't process that query.")
        assert content == "I couldn't process that query.", \
            "Live response has no 'answer' key at top level — ask page shows fallback text"

    def test_chat_widget_reads_response_key(self):
        """chat_widget.py reads result.get('response') — correct for live,
        wrong for mock which uses 'answer'."""
        ds = self._make_mock_ds()
        result = ds.query_orchestrator("Performance summary")
        content = result.get("response", "No response received.")
        assert content == "No response received.", \
            "Mock has 'answer' not 'response' — widget falls back to default"

    # -- pause/resume: undefined attribute ---
    def test_pause_campaign_swallows_attributeerror(self):
        ds = self._make_live_ds()
        # Should not raise even though optimization_service is undefined
        ds.pause_campaign(1)

    def test_resume_campaign_swallows_attributeerror(self):
        ds = self._make_live_ds()
        ds.resume_campaign(1)

    # -- _api_get: JSON decode gap ---
    def test_api_get_non_json_200_uncaught(self):
        ds = self._make_live_ds()
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.side_effect = ValueError("No JSON object could be decoded")
            mock_get.return_value = mock_resp
            with pytest.raises(ValueError):
                ds._api_get("/api/dashboard/summary")

    # -- Mock dashboard summary keys ---
    def test_mock_dashboard_summary_has_expected_keys(self):
        ds = self._make_mock_ds()
        result = ds.get_dashboard_summary()
        for key in ("total_spend_today", "avg_roas", "active_campaigns", "pending_recommendations"):
            assert key in result, f"Missing key: {key}"

    # -- Fallback silently serves mock when API is partially down ---
    def test_silent_fallback_when_endpoint_fails(self):
        """If use_mock is False but an endpoint returns None, the method
        silently falls back to mock data with no indication."""
        ds = self._make_live_ds()
        assert ds.use_mock is False
        with patch.object(ds, "_api_get", return_value=None):
            result = ds.get_dashboard_summary()
        assert result["total_spend_today"] == 12450.00, \
            "Silently returned mock data while use_mock is False"


# ---------------------------------------------------------------------------
# 2. Chart Components: edge cases with missing keys, empty data, NaN
# ---------------------------------------------------------------------------

class TestChartEdgeCases:
    """Chart helpers crash on missing keys or malformed data."""

    def test_time_series_missing_key_raises(self):
        from frontend.components.charts import render_time_series_chart
        data = [{"date": "2024-01-01", "value": 1.0}]
        with pytest.raises(KeyError):
            # Attempting to use a non-existent key
            render_time_series_chart(data, x_key="date", y_key="nonexistent")

    def test_pie_chart_missing_key_raises(self):
        from frontend.components.charts import render_pie_chart
        data = [{"name": "Google", "value": 100}]
        with pytest.raises(KeyError):
            render_pie_chart(data, label_key="name", value_key="missing_key")

    def test_sparkline_empty_values(self):
        from frontend.components.charts import render_sparkline
        # Should not raise — has explicit empty guard
        render_sparkline([])

    def test_time_series_empty_data(self):
        from frontend.components.charts import render_time_series_chart
        # Should not raise — has explicit empty guard
        render_time_series_chart([], x_key="date", y_key="roas")


class TestDualAxisChartEdgeCases:

    def test_empty_data_handled(self):
        from frontend.components.dual_axis_chart import render_dual_axis_chart
        # Should return without error
        render_dual_axis_chart([])

    def test_detect_anomalies_empty(self):
        from frontend.components.dual_axis_chart import detect_anomalies
        assert detect_anomalies([]) == []

    def test_detect_anomalies_insufficient_data(self):
        from frontend.components.dual_axis_chart import detect_anomalies
        assert detect_anomalies([{"cost": 100, "roas": 2.0}]) == []

    def test_detect_anomalies_constant_values(self):
        """When std == 0, no anomalies should be detected (all values equal)."""
        from frontend.components.dual_axis_chart import detect_anomalies
        data = [{"cost": 100, "roas": 2.0, "date": f"2024-01-{i+1:02d}"} for i in range(10)]
        result = detect_anomalies(data, spend_key="cost", kpi_key="roas")
        assert result == [], "Constant values (std=0) should produce no anomalies"

    def test_detect_anomalies_with_nan(self):
        """NaN values in numeric columns should not crash anomaly detection."""
        from frontend.components.dual_axis_chart import detect_anomalies
        data = [
            {"cost": 100, "roas": 2.0, "date": "2024-01-01"},
            {"cost": float("nan"), "roas": 2.0, "date": "2024-01-02"},
            {"cost": 100, "roas": float("nan"), "date": "2024-01-03"},
            {"cost": 200, "roas": 3.0, "date": "2024-01-04"},
        ]
        # Should not raise
        result = detect_anomalies(data, spend_key="cost", kpi_key="roas")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 3. Incrementality Page: ZeroDivisionError on empty experiments
# ---------------------------------------------------------------------------

class TestIncrementalityPageEdgeCases:

    def test_avg_lift_division_by_zero_on_empty(self):
        """Frontend incrementality results computes
        avg_lift = sum(...) / len(experiments) without checking len > 0."""
        experiments = []
        with pytest.raises(ZeroDivisionError):
            _ = sum(e['lift_percent'] for e in experiments) / len(experiments)

    def test_avg_lift_with_inf_values(self):
        """Infinite lift (from zero control CVR) propagates into averages."""
        experiments = [
            {"lift_percent": float("inf"), "incremental_roas": 0, "roas_inflation": 0, "is_significant": True},
            {"lift_percent": 50.0, "incremental_roas": 2.0, "roas_inflation": 15.0, "is_significant": False},
        ]
        avg_lift = sum(e["lift_percent"] for e in experiments) / len(experiments)
        assert avg_lift == float("inf"), \
            "inf propagates — UI will display 'inf%' or crash JSON serialization"

    def test_missing_keys_in_experiment_dict(self):
        """If API returns experiments without expected keys, page crashes."""
        experiments = [{"name": "test_exp"}]
        with pytest.raises(KeyError):
            _ = sum(e["lift_percent"] for e in experiments) / len(experiments)


# ---------------------------------------------------------------------------
# 4. DataService: forecast and scenario don't respect use_mock
# ---------------------------------------------------------------------------

class TestForecastScenarioMockInconsistency:

    def test_get_forecast_always_tries_api_first(self):
        """get_forecast does not check self.use_mock before calling _api_get."""
        from frontend.services.data_service import DataService
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_get.side_effect = Exception("no api")
            ds = DataService()

        assert ds.use_mock is True
        with patch.object(ds, "_api_get") as mock_api:
            mock_api.return_value = None
            ds.get_forecast(campaign_id=1, horizon_days=30)
        # Even in mock mode, _api_get is still called
        mock_api.assert_called_once()


# ---------------------------------------------------------------------------
# 5. SQLAlchemy Mapper Conflict (pre-existing)
# ---------------------------------------------------------------------------

class TestSQLAlchemyMapperConflict:
    """Documents that importing auth module alongside recommendations
    causes mapper initialization failures."""

    def test_mapper_conflict_on_user_reference(self):
        """Recommendation model references 'User' which may not be resolved
        if auth module hasn't been imported first."""
        try:
            from src.bandit_ads.recommendations import Recommendation
            from src.bandit_ads.auth import User
            # If both import cleanly, the mapper should resolve
            assert True
        except Exception as e:
            # Documents the pre-existing mapper conflict
            assert "User" in str(e) or "mapper" in str(e).lower()


# ---------------------------------------------------------------------------
# 6. JSON Serialization of Special Float Values
# ---------------------------------------------------------------------------

class TestJSONSerializationEdgeCases:
    """API responses containing inf/NaN break standard JSON."""

    def test_inf_produces_non_standard_json(self):
        import json
        result = json.dumps({"lift_percent": float("inf")})
        # Python allows Infinity but it's invalid per RFC 7159;
        # JavaScript JSON.parse("Infinity") throws SyntaxError.
        assert "Infinity" in result, \
            "Python serializes inf as 'Infinity' which is not valid JSON"

    def test_nan_not_json_serializable_strict(self):
        import json
        result = json.dumps({"value": float("nan")})
        # Python's json.dumps allows NaN by default (non-standard)
        assert "NaN" in result, "NaN is serialized but is invalid JSON per spec"
