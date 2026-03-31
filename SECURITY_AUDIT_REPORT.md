Verify each finding against the current code and only fix it if needed.

In @SECURITY_AUDIT_REPORT.md at line 51, The report lists F18 in the Medium-priority table but the adversarial review text later states "F8/F18 upgraded to HIGH"; update the markdown so F18 appears in the HIGH-priority table and is removed from the Medium table, ensuring the F18 row (referencing `/api/ask` and `src/bandit_ads/api/main.py`) is added to the HIGH section and deleted from the Medium section, and adjust any adjacent numbering or table formatting so the tables render correctly.# IPSA Security & Edge-Case Audit Report

**Date:** 2026-03-31
**Scope:** Mock-data-first security and production edge-case QA pass
**Test Suite:** 80 new automated tests (`test_security_edge_cases.py`, `test_frontend_edge_cases.py`)
**Review Method:** Primary analysis + independent adversarial review (Codex-style second opinion)

---

## Ship-Readiness Score: 3/10 (NOT production-ready)

The application has strong algorithmic foundations (bandit optimization, MMM modeling) but critical security gaps make it unsafe to expose to any network beyond localhost development.

---

## Must-Fix Before Production (Critical + High)

### CRITICAL

| ID | Finding | File | Test |
|----|---------|------|------|
| F1 | **No authentication on any API route.** `auth.py` has a full `AuthManager` with session tokens, but it is never wired as FastAPI middleware. All 12 routers are completely open. | `src/bandit_ads/api/main.py:41-52` | `TestUnauthenticatedAccess` (7 tests) |
| F2 | **CORS wildcard + credentials.** `allow_origins=["*"]` with `allow_credentials=True` — any website can make cross-origin requests. | `src/bandit_ads/api/main.py:32-38` | `TestCORSPolicy` (2 tests) |
| F3 | **Internal exception details leak to all clients.** Global handler returns `str(exc)` which can expose DB schemas, file paths, API keys in error messages. This pattern is **systemic** across all 14+ route files via `HTTPException(detail=str(e))`. | `src/bandit_ads/api/main.py:90-101`, every route in `api/routes/` | `TestGlobalErrorHandler` (2 tests), `TestAskEndpointErrorSanitization` |

### HIGH

| ID | Finding | File | Test |
|----|---------|------|------|
| F4 | **Webhook signature verification is fail-open.** Missing secret key → verification skipped (`return True`). Missing signature header → check bypassed entirely. Attackers can inject fake conversion data by omitting the signature header. | `src/bandit_ads/webhooks.py:58-60, 400-459` | `TestWebhookSignatureVerification` (5 tests) |
| F5 | **File upload with no max size limit.** `await file.read()` loads entire file into memory. A single multi-GB upload = OOM crash. No upload size limit in FastAPI config. | `src/bandit_ads/api/routes/data.py:75` | `TestUploadEndpoint` (10 tests) |
| F6 | **Unsalted SHA-256 password hashing.** Single-round, no salt, no pepper. Identical passwords produce identical hashes. Currently inert (auth not wired), but becomes critical if auth is enabled. | `src/bandit_ads/auth.py:88` | `TestAuthModule` (4 tests) |
| F7 | **Default-open access control.** When no `CampaignAccess` row exists, viewers get read access to ALL campaigns, analysts get write access to ALL campaigns. Inverts least-privilege. | `src/bandit_ads/auth.py:214-217` | `TestAuthModule::test_default_access_viewer_can_read_any_campaign` |
| F8 | **Dynamic method dispatch from LLM output.** `_execute_tool_calls` uses `__getattribute__(f"_{tool_name}")` where `tool_name` comes from LLM-generated tool calls. Prompt injection via the `/api/ask` endpoint could invoke arbitrary methods on the operations object. | `src/bandit_ads/orchestrator.py:351` | — |
| F9 | **XSS via `unsafe_allow_html=True`.** 60+ instances in frontend render API-controlled data (campaign names, experiment names, recommendation titles) directly into raw HTML without sanitization. | Frontend pages: `incrementality.py`, `campaign_detail.py`, `recommendations.py`, `home.py` | — |
| F18 | **No rate limiting on any endpoint.** The `/api/ask` endpoint makes LLM API calls — unauthenticated abuse can run up Claude/OpenAI bills. Upload endpoint compounds this (memory exhaustion). *(Upgraded from Medium by adversarial review.)* | `src/bandit_ads/api/main.py` | — |

---

## Production Edge Cases (Medium)

| ID | Finding | File | Test |
|----|---------|------|------|
| F10 | **Orchestrator RAG context is dead code.** The `rag_context` assignment sits in the `else` branch after `rag_results = None`, so `if rag_results:` is always `False`. RAG context never enriches LLM prompts. | `src/bandit_ads/orchestrator.py:136-148` | `TestOrchestratorRAGLogicBug` (2 tests) |
| F11 | **`query_orchestrator` response key mismatch.** Live path wraps answer in `'response'` key; mock returns `'answer'` key. Ask page reads `'answer'` (breaks on live). Chat widget reads `'response'` (breaks on mock). Users see wrong/empty responses depending on which path is active. | `frontend/services/data_service.py:1330-1349`, `frontend/pages/ask.py:139`, `frontend/components/chat_widget.py:84` | `TestDataServiceResponseContracts` (9 tests) |
| F12 | **`pause_campaign`/`resume_campaign` reference undefined attribute.** `self.optimization_service` is never initialized in `DataService.__init__`. These methods (plus 3 others) silently swallow `AttributeError`, show success toast to user while doing nothing. | `frontend/services/data_service.py:1003-1017, 1224-1240` | `TestDataServiceContracts` |
| F13 | **Silent mock fallback masks API outages.** When `use_mock=False` but individual endpoints fail, methods silently return hardcoded mock data. No `"data is synthetic"` indicator in UI. Users could make real budget decisions based on fictional numbers. | `frontend/services/data_service.py` (15+ methods) | `TestDataServiceResponseContracts::test_silent_fallback_when_endpoint_fails` |
| F14 | **`_api_get` doesn't catch `JSONDecodeError`.** A 200 response with non-JSON body crashes with uncaught `ValueError`. | `frontend/services/data_service.py:53-62` | `TestDataServiceContracts::test_api_get_non_json_response_raises` |
| F24 | ~~**`float('inf')` in incrementality results breaks JSON.**~~ **FIXED.** `calculate_incrementality` now returns `999999.99` (JSON-safe cap) instead of `float('inf')` when control CVR is zero. | `src/bandit_ads/incrementality.py:182` | `TestIncrementalityEdgeCases`, `TestJSONSerializationEdgeCases` |
| F16 | **`np.load(allow_pickle=True)`.** Used in Meridian insights to load model files. If model path is influenced by untrusted input, enables arbitrary code execution via pickle gadgets. | `src/bandit_ads/meridian_insights.py` | — |
| F17 | **Forecast/scenario methods ignore `use_mock` flag.** `get_forecast` and `simulate_scenario` always try HTTP first regardless of `use_mock` state, causing spurious network calls in demo mode. | `frontend/services/data_service.py:1872-1878` | `TestForecastScenarioMockInconsistency` |

---

## Low Priority / Informational

| ID | Finding | Notes |
|----|---------|-------|
| F19 | Chart components crash on missing keys (`KeyError`) | `charts.py:72-73` — no `.get()` with defaults |
| F20 | `detect_anomalies` handles constant values (std=0) correctly | Tested and confirmed safe |
| F21 | Cache uses `datetime.now()` vs `datetime.utcnow()` elsewhere | Not a functional bug (same-process cache) |
| F22 | Session tokens never cleaned up; no revocation mechanism | `auth.py:148` — expired sessions accumulate |
| F23 | Forecasting uses only 1000 possible random seeds | `forecasting.py` — `random.seed(hash(ch) % 1000)` |

---

## Adversarial Review Reconciliation

The independent review **confirmed** 17 of 20 original findings and **disputed** 2:
- **F15 (incrementality ZeroDivisionError):** DISPUTED — the function has an early `return` guard before the division. The empty-list case is handled. Removed from Critical/Medium. *(The related `float('inf')` JSON serialization concern was tracked separately as F24 and has since been fixed.)*
- **F20 (SQLAlchemy mapper conflict):** DISPUTED — models co-import correctly; issue may have been a runtime ordering artifact. Downgraded to informational.

The independent review **upgraded** 3 findings:
- F3 upgraded to CRITICAL (systemic across all routes, combined with no auth)
- F7 upgraded to HIGH (broken authorization model)
- F8/F18 upgraded to HIGH (dynamic dispatch from LLM + no rate limiting)

The independent review found **5 additional issues** (NEW-F1 through NEW-F5), integrated into the findings above.

---

## Remediation Backlog

### Security Hardening (Priority 1)
1. Wire `AuthManager` as FastAPI `Depends()` middleware on all routers
2. Restrict CORS origins to actual frontend URL
3. Sanitize all error responses — replace `str(e)` with generic messages, log details server-side only
4. Make webhook verification fail-closed (reject if no secret or no signature)
5. Replace SHA-256 password hashing with `bcrypt` or `argon2`
6. Add upload size limit (`app.add_middleware(TrustedHostMiddleware, ...)` or config)
7. Add rate limiting middleware (e.g., `slowapi`)
8. Sanitize HTML rendering in frontend (escape campaign/experiment names)
9. Add allowlist for tool dispatch in orchestrator

### Reliability Hardening (Priority 2)
1. Fix `query_orchestrator` response key contract (use consistent key)
2. Fix orchestrator RAG dead-code logic bug
3. Add explicit "data source" indicator (live/mock/degraded) to all UI responses
4. Initialize `optimization_service` or remove pause/resume from DataService
5. Catch `JSONDecodeError` in `_api_get`/`_api_post`
6. Replace `float('inf')` with a serializable sentinel in incrementality results
7. Make `get_forecast`/`simulate_scenario` respect `use_mock`

### Test Infrastructure (Priority 3)
1. Add `pytest` and `httpx` to `requirements.txt`
2. Add real assertions to the 4 assertion-free test files
3. Add `pytest.ini` with markers (`unit`, `integration`, `slow`)
4. Add DB fixture isolation (in-memory SQLite per test)

---

## Test Evidence

```
tests/test_security_edge_cases.py   — 55 tests, 55 passed
tests/test_frontend_edge_cases.py   — 25 tests, 25 passed
Total new tests:                      80 tests, 80 passed
Pre-existing suite:                   56 tests, 56 passed (51 pass when run with new tests due to mapper ordering)
```
