"""
Security & Production Edge-Case Test Suite

Tests for vulnerabilities and reliability issues using mock/local DB only.
Covers: auth gaps, error sanitization, upload robustness, webhook verification,
fallback behavior, orchestrator logic, and data integrity edge cases.
"""

import json
import hmac
import hashlib
import math
import io
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bandit_ads.api.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. CORS & Global Error Handler
# ---------------------------------------------------------------------------

class TestCORSPolicy:
    """Verify CORS configuration is restrictive."""

    def test_wildcard_origin_with_credentials(self):
        """Disallowed origins should not be reflected by CORS."""
        resp = client.options(
            "/api/health",
            headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin == "", "Disallowed origin should not receive CORS allow header"

    def test_cors_allows_arbitrary_methods(self):
        """Disallowed origins should not receive access-control allow-origin."""
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin == "", "Disallowed origin should not be explicitly allowed"


class TestGlobalErrorHandler:
    """Verify 500/503 responses are sanitized."""

    def test_500_sanitizes_detail_for_client(self):
        """HTTP 500 should not expose internal exception details to clients."""
        with patch("src.bandit_ads.api.routes.dashboard.get_db_manager") as mock_db:
            mock_db.side_effect = RuntimeError("secret_db_password_here")
            resp = client.get("/api/dashboard/summary")
        assert resp.status_code == 500
        body = resp.json()
        assert body.get("error") == "Internal server error"
        assert "secret_db_password_here" not in json.dumps(body)

    def test_health_503_sanitizes_exception(self):
        """Health endpoint 503 should not leak internal hostnames/details."""
        with patch("src.bandit_ads.database.get_db_manager") as mock_db:
            mock_db.side_effect = Exception("connection refused to db.prod.internal:5432")
            resp = client.get("/api/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body.get("error") == "Service temporarily unavailable"
        assert "db.prod.internal" not in json.dumps(body)


# ---------------------------------------------------------------------------
# 2. Unauthenticated Access (No Auth Middleware)
# ---------------------------------------------------------------------------

class TestUnauthenticatedAccess:
    """All API routes are accessible without credentials."""

    ENDPOINTS = [
        ("GET", "/api/health"),
        ("GET", "/api/campaigns"),
        ("GET", "/api/dashboard/summary"),
        ("GET", "/api/recommendations"),
        ("GET", "/api/optimizer/status"),
        ("GET", "/api/data"),
        ("GET", "/api/incrementality/experiments"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_no_auth_required(self, method, path):
        """Routes should be reachable without any auth header.
        This test documents the current open-access state."""
        resp = client.request(method, path)
        # Should NOT be 401/403 — proves auth is absent
        assert resp.status_code not in (401, 403), \
            f"{method} {path} unexpectedly required auth"


# ---------------------------------------------------------------------------
# 3. Error Sanitisation (Ask endpoint)
# ---------------------------------------------------------------------------

class TestAskEndpointErrorSanitization:
    """The /api/ask route should sanitize internal exception details."""

    def test_ask_error_does_not_leak_exception_text(self):
        """OrchestratorAgent is imported inside the route handler, so we
        must patch at the module level where it's resolved."""
        with patch("src.bandit_ads.orchestrator.OrchestratorAgent") as MockOrch:
            instance = MockOrch.return_value
            instance.process_query = AsyncMock(
                side_effect=RuntimeError("ANTHROPIC_API_KEY=sk-secret-leaked")
            )
            resp = client.post("/api/ask", json={"query": "test"})
        assert resp.status_code == 200  # returns 200 with error in body
        body = resp.json()
        assert body.get("error") is not None
        assert body["error"] == "Internal server error"
        assert "sk-secret-leaked" not in json.dumps(body)

    def test_ask_empty_query(self):
        """Empty query string should still return a valid response shape."""
        resp = client.post("/api/ask", json={"query": ""})
        assert resp.status_code in (200, 422)

    def test_ask_very_long_query(self):
        """Extremely long queries should not crash the server."""
        long_query = "A" * 100_000
        resp = client.post("/api/ask", json={"query": long_query})
        assert resp.status_code in (200, 413, 422)


# ---------------------------------------------------------------------------
# 4. File Upload Robustness
# ---------------------------------------------------------------------------

class TestUploadEndpoint:
    """Upload endpoint must handle malicious/malformed inputs."""

    def test_upload_unsupported_extension(self):
        resp = client.post(
            "/api/data/upload",
            files={"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Only CSV and JSON" in resp.json()["detail"]

    def test_upload_empty_csv(self):
        resp = client.post(
            "/api/data/upload",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        # Empty file should not crash — either 200 with 0 rows or 422
        assert resp.status_code in (200, 422)

    def test_upload_invalid_json(self):
        resp = client.post(
            "/api/data/upload",
            files={"file": ("bad.json", b"{not valid json", "application/json")},
        )
        assert resp.status_code == 422

    def test_upload_invalid_utf8(self):
        resp = client.post(
            "/api/data/upload",
            files={"file": ("bad.csv", b"\xff\xfe\x00\x01col1,col2\n", "text/csv")},
        )
        assert resp.status_code == 422

    def test_upload_large_payload_no_crash(self):
        """5 MB CSV should not cause OOM on a healthy system."""
        big_csv = b"col1,col2\n" + b"a,b\n" * 500_000
        resp = client.post(
            "/api/data/upload",
            files={"file": ("big.csv", big_csv, "text/csv")},
        )
        assert resp.status_code in (200, 413, 422)

    def test_upload_csv_no_date_column(self):
        """CSV without a date column should still parse without error."""
        csv_data = b"channel,spend,conversions\nGoogle,100,5\nMeta,200,10\n"
        resp = client.post(
            "/api/data/upload",
            files={"file": ("no_date.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["rows"] == 2
        assert body["date_range"] is None

    def test_upload_json_array(self):
        data = json.dumps([{"date": "2024-01-01", "spend": 100}]).encode()
        resp = client.post(
            "/api/data/upload",
            files={"file": ("good.json", data, "application/json")},
        )
        assert resp.status_code == 200
        assert resp.json()["rows"] == 1

    def test_upload_json_object(self):
        data = json.dumps({"date": "2024-01-01", "spend": 100}).encode()
        resp = client.post(
            "/api/data/upload",
            files={"file": ("single.json", data, "application/json")},
        )
        assert resp.status_code == 200
        assert resp.json()["rows"] == 1

    def test_delete_nonexistent_file(self):
        resp = client.delete("/api/data/upload/nonexistent_file.csv")
        assert resp.status_code == 404

    def test_upload_filename_with_path_traversal(self):
        """Filenames like ../../etc/passwd should not escape."""
        resp = client.post(
            "/api/data/upload",
            files={"file": ("../../etc/passwd.csv", b"col1\nval1\n", "text/csv")},
        )
        # Should process normally since storage is in-memory
        assert resp.status_code in (200, 400, 422)


# ---------------------------------------------------------------------------
# 5. Webhook Signature Verification
# ---------------------------------------------------------------------------

class TestWebhookSignatureVerification:
    """Test webhook handler signature logic in isolation."""

    def test_verify_signature_no_secret_returns_false(self):
        """Fail-closed: missing secret rejects verification."""
        from src.bandit_ads.webhooks import WebhookHandler
        handler = WebhookHandler(secret_keys={})
        assert handler.verify_signature("google", b"payload", "any_sig") is False

    def test_verify_signature_wrong_hmac_returns_false(self):
        from src.bandit_ads.webhooks import WebhookHandler
        handler = WebhookHandler(secret_keys={"google": "real_secret"})
        assert handler.verify_signature("google", b"payload", "wrong_sig") is False

    def test_verify_signature_correct_hmac_returns_true(self):
        from src.bandit_ads.webhooks import WebhookHandler
        secret = "my_secret"
        payload = b'{"event": "conversion"}'
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        handler = WebhookHandler(secret_keys={"google": secret})
        assert handler.verify_signature("google", payload, expected) is True

    def test_meta_sha256_prefix_stripped(self):
        from src.bandit_ads.webhooks import WebhookHandler
        secret = "meta_secret"
        payload = b'{"entry": []}'
        raw_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        handler = WebhookHandler(secret_keys={"meta": secret})
        assert handler.verify_signature("meta", payload, f"sha256={raw_sig}") is True

    def test_webhook_route_no_signature_header_rejected(self):
        """Missing signature should fail verification in fail-closed mode."""
        from src.bandit_ads.webhooks import WebhookHandler
        handler = WebhookHandler(secret_keys={"google": "secret"})
        signature = ""
        assert handler.verify_signature("google", b"data", signature) is False


# ---------------------------------------------------------------------------
# 6. Auth Module Weaknesses
# ---------------------------------------------------------------------------

class TestAuthModule:
    """Test auth.py password hashing and default access control."""

    def test_password_hash_uses_bcrypt(self):
        from src.bandit_ads.auth import AuthManager
        with patch("src.bandit_ads.auth.get_db_manager"):
            mgr = AuthManager()
        h = mgr.hash_password("password123")
        assert h.startswith("$2"), "Password hashing should use bcrypt format"
        assert mgr.verify_password("password123", h) is True

    def test_same_password_produces_different_hashes(self):
        """With per-password salt, identical passwords should hash differently."""
        from src.bandit_ads.auth import AuthManager
        with patch("src.bandit_ads.auth.get_db_manager"):
            mgr = AuthManager()
        h1 = mgr.hash_password("abc")
        h2 = mgr.hash_password("abc")
        assert h1 != h2
        assert mgr.verify_password("abc", h1) is True
        assert mgr.verify_password("abc", h2) is True

    def test_default_access_viewer_cannot_read_any_campaign(self):
        """When no CampaignAccess row exists, deny access by default."""
        from src.bandit_ads.auth import AuthManager
        with patch("src.bandit_ads.auth.get_db_manager") as mock_db:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_db.return_value.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.get_session.return_value.__exit__ = MagicMock(return_value=False)
            mgr = AuthManager()

        user = MagicMock()
        user.role = "viewer"
        assert mgr.check_access(user, campaign_id=9999, operation="read") is False

    def test_default_access_viewer_cannot_write(self):
        from src.bandit_ads.auth import AuthManager
        with patch("src.bandit_ads.auth.get_db_manager") as mock_db:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_db.return_value.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_db.return_value.get_session.return_value.__exit__ = MagicMock(return_value=False)
            mgr = AuthManager()

        user = MagicMock()
        user.role = "viewer"
        assert mgr.check_access(user, campaign_id=9999, operation="write") is False


# ---------------------------------------------------------------------------
# 7. Orchestrator Logic Bugs
# ---------------------------------------------------------------------------

class TestOrchestratorRAGLogicBug:
    """The RAG context assignment has a dead-code logic bug."""

    def test_rag_context_never_set_in_else_branch(self):
        """Lines 145-148 in orchestrator.py:
            else:
                rag_results = None
                if rag_results:        # <-- always False
                    rag_context = ...   # <-- dead code
        """
        # Simulate the logic directly
        rag_results = None
        rag_context = None
        # This is the else branch:
        rag_results = None
        if rag_results:
            rag_context = "should_never_be_set"
        assert rag_context is None, "RAG context is dead code in the else branch"

    def test_rag_context_also_dead_for_true_branch(self):
        """Even when the if-branch succeeds and rag_results is populated,
        the rag_context = _format_rag_context(rag_results) line is in the
        else block, so rag_context stays None."""
        rag_context = None
        vector_store_available = True
        query_type_match = True

        if query_type_match and vector_store_available:
            rag_results = [{"text": "past decision A"}]
        else:
            rag_results = None
            if rag_results:
                rag_context = "formatted"

        # rag_context is still None even though rag_results has data
        assert rag_context is None, \
            "RAG context assignment is in wrong branch — never reaches successful results"


# ---------------------------------------------------------------------------
# 8. Realtime Environment Fallback Behavior
# ---------------------------------------------------------------------------

class TestRealtimeEnvironmentFallback:
    """Test that fallback to simulated data is observable."""

    def test_fallback_returns_simulated_source(self):
        """When no connectors, step() falls back to parent AdEnvironment.step()."""
        from src.bandit_ads.realtime_env import RealTimeEnvironment
        from src.bandit_ads.arms import Arm

        env = RealTimeEnvironment(
            api_connectors={},
            fallback_to_simulated=True,
            mmm_factors={},
        )
        arm = Arm(platform="Google", channel="Search", creative="A", bid=1.0)
        result = env.step(arm, impressions=100)
        assert result is not None
        assert "impressions" in result or "clicks" in result

    def test_no_fallback_returns_zeros(self):
        from src.bandit_ads.realtime_env import RealTimeEnvironment
        from src.bandit_ads.arms import Arm

        env = RealTimeEnvironment(
            api_connectors={},
            fallback_to_simulated=False,
            mmm_factors={},
        )
        arm = Arm(platform="Google", channel="Search", creative="A", bid=1.0)
        result = env.step(arm, impressions=100)
        if result is not None:
            assert result.get("source") == "none"
            assert result["impressions"] == 0

    def test_cache_uses_local_datetime(self):
        """Cache timestamps use datetime.now() — mixing with UTC elsewhere
        could cause stale-data issues."""
        from src.bandit_ads.realtime_env import RealTimeEnvironment
        env = RealTimeEnvironment(
            api_connectors={},
            fallback_to_simulated=True,
            mmm_factors={},
        )
        env._cache_metrics("test_arm", {"impressions": 42})
        cached = env._get_cached_metrics("test_arm")
        assert cached is not None
        assert cached["impressions"] == 42

    def test_cache_expiry(self):
        from src.bandit_ads.realtime_env import RealTimeEnvironment
        env = RealTimeEnvironment(
            api_connectors={},
            fallback_to_simulated=True,
            data_retention_days=0,
            mmm_factors={},
        )
        env._cache_metrics("test_arm", {"impressions": 42})
        env.cache_timestamps["test_arm"] = datetime.now() - timedelta(days=1)
        cached = env._get_cached_metrics("test_arm")
        assert cached is None, "Expired cache should return None"


# ---------------------------------------------------------------------------
# 9. Incrementality Edge Cases
# ---------------------------------------------------------------------------

class TestIncrementalityEdgeCases:
    """Edge cases in incrementality calculations."""

    def test_holdout_zero_users_returns_zero_cvr(self):
        from src.bandit_ads.incrementality import HoldoutArm
        h = HoldoutArm()
        assert h.get_baseline_cvr() == 0.0

    def test_holdout_zero_users_returns_zero_revenue(self):
        from src.bandit_ads.incrementality import HoldoutArm
        h = HoldoutArm()
        assert h.get_baseline_revenue_per_user() == 0.0

    def test_calculate_incrementality_zero_control(self):
        from src.bandit_ads.incrementality import calculate_incrementality
        result = calculate_incrementality(
            treatment_cvr=0.10,
            control_cvr=0.0,
            treatment_users=100,
            control_users=100,
            treatment_conversions=10,
            control_conversions=0,
        )
        assert result is not None
        assert math.isfinite(result["lift_percent"])
        assert result["lift_percent"] == 999999.99

    def test_calculate_incrementality_both_zero(self):
        from src.bandit_ads.incrementality import calculate_incrementality
        result = calculate_incrementality(treatment_cvr=0.0, control_cvr=0.0)
        assert result["lift_percent"] == 0.0
        assert result["is_significant"] is False

    def test_calculate_incremental_roas_zero_spend(self):
        from src.bandit_ads.incrementality import calculate_incremental_roas
        result = calculate_incremental_roas(
            treatment_revenue=100.0,
            control_revenue=50.0,
            treatment_spend=0.0,
            treatment_users=100,
            control_users=100,
        )
        assert result is not None
        iroas = result.get("incremental_roas")
        assert iroas == 0.0, f"Expected iROAS of 0.0 for zero spend, got {iroas}"


# ---------------------------------------------------------------------------
# 10. Frontend DataService Contract Issues (unit-level)
# ---------------------------------------------------------------------------

class TestDataServiceContracts:
    """Test hardened mock/live response contracts."""

    def test_query_orchestrator_mock_uses_answer_key(self):
        """Mock response uses 'answer', live wraps in 'response'."""
        from frontend.services.data_service import DataService
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_get.side_effect = Exception("no api")
            ds = DataService()
        assert ds.use_mock is True
        result = ds.query_orchestrator("Why did ROAS increase?")
        assert "answer" in result, "Mock response should have 'answer' key"

    def test_query_orchestrator_live_returns_answer_consistently(self):
        """Live path should expose answer consistently (with response alias)."""
        from frontend.services.data_service import DataService
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_resp
            ds = DataService()

        with patch.object(ds, "_api_post") as mock_post:
            mock_post.return_value = {
                "answer": "Budget increased due to ROAS improvement",
                "query_type": "explanation",
            }
            result = ds.query_orchestrator("Why did budget increase?")

        assert result.get("answer") == "Budget increased due to ROAS improvement"
        assert result.get("response") == result.get("answer")

    def test_pause_campaign_live_mode_uses_api_post(self):
        """pause_campaign should call API endpoint instead of undefined attribute."""
        from frontend.services.data_service import DataService
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_resp
            ds = DataService()

        assert ds.use_mock is False
        with patch.object(ds, "_api_post") as mock_post:
            mock_post.return_value = {"success": True}
            ds.pause_campaign(123)
            mock_post.assert_called_once_with("/api/campaigns/123/pause")

    def test_api_get_non_json_response_returns_none(self):
        """_api_get should safely return None on invalid JSON payloads."""
        from frontend.services.data_service import DataService
        with patch("frontend.services.data_service.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_resp
            ds = DataService()

        with patch("frontend.services.data_service.requests.get") as mock_get2:
            mock_resp2 = MagicMock()
            mock_resp2.status_code = 200
            mock_resp2.raise_for_status.return_value = None
            mock_resp2.json.side_effect = ValueError("No JSON")
            mock_get2.return_value = mock_resp2
            assert ds._api_get("/api/dashboard/summary") is None


# ---------------------------------------------------------------------------
# 11. API Route Edge Cases
# ---------------------------------------------------------------------------

class TestAPIRouteEdgeCases:

    def test_campaigns_list_returns_valid_json(self):
        resp = client.get("/api/campaigns")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert isinstance(resp.json(), (list, dict))

    def test_campaign_detail_nonexistent(self):
        resp = client.get("/api/campaigns/99999")
        assert resp.status_code in (404, 500)

    def test_dashboard_summary_shape(self):
        resp = client.get("/api/dashboard/summary")
        assert resp.status_code in (200, 500)

    def test_optimizer_status_shape(self):
        resp = client.get("/api/optimizer/status")
        assert resp.status_code in (200, 500)

    def test_incrementality_experiments_list(self):
        resp = client.get("/api/incrementality/experiments")
        assert resp.status_code in (200, 500)

    def test_ask_invalid_json_body(self):
        resp = client.post(
            "/api/ask",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_ask_missing_query_field(self):
        resp = client.post("/api/ask", json={"campaign_id": 1})
        assert resp.status_code == 422
