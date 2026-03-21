# Ipsa Core Differentiators – Full Audit

This document reports the implementation status of Ipsa’s four core differentiators, which files/functions deliver them, what’s missing, and the single most important next step to complete each.

---

## 1. Real-Time ML Optimization

**Question:** Is Thompson Sampling running and allocating budgets in real time across platforms? Is the loop scheduled/triggered? Are budget changes pushed to Google Ads, Meta, and TTD automatically? Is there lag or a manual step between recommendation and execution?

### What Exists

| Component | Location | Behavior |
|-----------|----------|----------|
| Optimization loop on a schedule | `src/bandit_ads/optimization_service.py`: `_optimization_loop()`, `_run_optimization_cycle()`, `start()` | Loop runs in a background thread; waits `optimization_interval_minutes` (default 15) between cycles. |
| Thompson Sampling allocation | `src/bandit_ads/agent.py`: `ThompsonSamplingAgent._allocate_budget()`, `select_arm()`, `update()` | Bandit allocates and updates; used inside `_optimize_campaign()` via `runner.agent`. |
| Single optimization step | `src/bandit_ads/optimization_service.py`: `_optimize_campaign()` | Selects arm, gets spend, calls `runner.environment.step()`, updates agent, records holdout if `IncrementalityAwareBandit`. |
| Campaign loading at startup | `optimization_service.py`: `_load_active_campaigns()` | Loads active campaign IDs from DB into `active_campaigns`. |
| Adding a campaign (runner creation) | `optimization_service.py`: `add_campaign(campaign_id, campaign_config)` | Builds `AdOptimizationRunner`, runs `setup_campaign()` (creates agent/arms/env), stores in `campaign_runners`. |
| Budget “update” in product flow | `src/bandit_ads/mcp_server_operations.py`: `update_campaign_budget()` | Creates a **recommendation** (“Review and approve to apply”); does **not** call platform APIs. |
| Apply recommendation | `src/bandit_ads/recommendations.py`: `apply_recommendation()` | For `ALLOCATION_CHANGE` and `BUDGET_ADJUSTMENT`: `# TODO: Implement allocation override` / `# TODO: Implement budget update` – no platform calls. |
| Platform connectors | `src/bandit_ads/api_connectors.py` | `GoogleAdsConnector`, `MetaAdsConnector`, `TradeDeskConnector`: have `get_campaign_metrics()`, `get_available_campaigns()`; **no** `set_campaign_budget()` or equivalent. |

### Gaps

1. **Runners never created in normal flow**  
   `start()` only calls `_load_active_campaigns()`, which fills `active_campaigns` from the DB. It does **not** call `add_campaign()`, so `campaign_runners` stays empty. In `_optimize_campaign()`, `runner = self.campaign_runners.get(campaign_id)` is always `None`, then “Runner not found” and the step returns without optimizing.

2. **No push to ad platforms**  
   After the bandit step, there is no call to Google/Meta/TTD to change campaign or ad group budgets. Connectors are read-only for campaign/budget. `update_campaign_budget()` and `apply_recommendation()` only create or handle recommendations; they do not execute budget changes via APIs.

3. **Manual step between recommendation and execution**  
   Budget changes require creating a recommendation and then “review and approve to apply”; applying is still unimplemented (TODO) and would not call platform APIs even if implemented.

### Status: **Partially implemented**

- **Implemented:** Scheduled optimization loop, Thompson Sampling agent, single-step optimization and holdout recording, `add_campaign` and runner setup, recommendation creation for budget changes.
- **Missing:** Wiring so that when the service starts (or when campaigns are activated), runners are created (e.g. from DB campaign config); implementation of budget push to Google/Meta/TTD in connectors and in apply flow; removal of manual approve step if “automatic” execution is required.

### Recommended next step (single most important)

**Wire campaign runners into the loop and add a single end-to-end “budget push” path.**  
Concretely: (1) When the optimization service starts (or when a campaign is set active), build full campaign config from DB (arms, budget, agent config, etc.) and call `add_campaign(campaign_id, campaign_config)` so `campaign_runners` is populated and the loop can run real optimization. (2) In one connector (e.g. Google Ads), implement a small method that sets campaign (or ad group) budget via the existing client and call it from a single place (e.g. after allocation change in `_optimize_campaign`, or from `apply_recommendation` when type is budget/adjustment). That establishes the pattern; Meta and TTD can follow.

---

## 2. Incrementality Testing That Feeds Back Into the Bandit Automatically

**Question:** Do incrementality results automatically update Thompson Sampling priors? Is `IncrementalityAwareBandit` the active agent? When an experiment completes and is significant, does it auto-trigger a prior update? Is there a background job or event that connects experiment completion to bandit recalibration, or is it manual?

### What Exists

| Component | Location | Behavior |
|-----------|----------|----------|
| IncrementalityAwareBandit as default agent | `src/bandit_ads/runner.py`: `setup_campaign()`, `use_incrementality = incrementality_config.get('enabled', True)` | If not contextual, `use_incrementality` defaults to `True` and `IncrementalityAwareBandit` is instantiated. |
| Prior update from experiment result | `src/bandit_ads/agent.py`: `IncrementalityAwareBandit.incorporate_incrementality(arm_key, experiment_result)` | Updates alpha/beta from incremental vs observed ROAS; only if `is_significant`; forces reallocation. |
| Holdout tracking during optimization | `src/bandit_ads/optimization_service.py`: `_record_holdout_metrics()` | Called from `_optimize_campaign()` when agent is `IncrementalityAwareBandit`; records to holdout arm and to DB for running experiments. |
| Apply results to bandit (HTTP) | `src/bandit_ads/api/routes/incrementality.py`: `POST /api/incrementality/apply` | Requires `experiment_id`, `campaign_id`; loads experiment, gets runner from `service.campaign_runners.get(campaign_id)`, calls `runner.agent.incorporate_incrementality(arm_key, experiment_result)` for each arm. **Manual**: frontend or user must call this. |
| Auto-complete experiments when duration ends | `src/bandit_ads/incrementality_jobs.py`: `check_and_complete_expired_experiments()` | Uses `get_expired_experiments()`, then `auto_complete_experiment(experiment_id)` (DB only: status + results). **Does not** call `incorporate_incrementality`. |
| Scheduler registration | `src/bandit_ads/scheduler.py`: `get_scheduler(..., register_incrementality_jobs=True)` | Registers hourly `incrementality_auto_complete` and 4-hourly `incrementality_platform_sync`. |
| Experiment completion logic | `src/bandit_ads/db_helpers.py`: `auto_complete_experiment()`, `update_experiment_results()` | Computes and persists lift, iROAS, significance, etc. No hook to bandit. |

### Gaps

1. **No automatic bandit update on experiment completion**  
   When an experiment is completed (by the hourly job or by `POST .../complete`), only the DB is updated. Nothing calls `incorporate_incrementality()` or the apply endpoint. So “apply to bandit” is **manual** (user clicks “Apply to Bandit” in UI, which calls `POST /api/incrementality/apply`).

2. **Apply depends on runner being in memory**  
   Apply endpoint uses `service.campaign_runners.get(request.campaign_id)`. If the optimization service was restarted or the campaign was never added via `add_campaign`, there is no runner and apply returns 404. So even manual apply can fail for campaigns that are not currently in the running optimizer.

### Status: **Partially implemented**

- **Implemented:** IncrementalityAwareBandit as default agent; holdout recording in the optimization cycle; apply endpoint and UI button; auto-complete of experiments (DB); scheduler jobs for completion and platform sync.
- **Missing:** A background or event-driven step that, when an experiment is marked completed and (optionally) significant, either calls the apply endpoint or directly calls `incorporate_incrementality()` for the right campaign/runner so that prior updates happen without user action.

### Recommended next step (single most important)

**Connect experiment completion to bandit prior update without manual action.**  
In `incrementality_jobs.check_and_complete_expired_experiments()`, after `auto_complete_experiment(experiment.id)` succeeds and the experiment is significant, get the campaign_id and (if the optimization service has a runner for that campaign) call `runner.agent.incorporate_incrementality(arm_key, experiment_result)` for the relevant arm(s), reusing the same payload structure as the apply endpoint. If you prefer to keep “apply” as the single place that touches the bandit, then from the job call an internal function or the apply endpoint (with experiment_id and campaign_id) so that one code path handles both manual and auto apply.

---

## 3. Plain-Language Explanations for Every Decision

**Question:** Does every budget change or recommendation produce a plain-language explanation via the LLM? Is the explanation triggered automatically on every allocation change? Are explanations stored and visible in the dashboard alongside each decision? Do they reference real reasons (saturation, seasonality, incrementality) or are they generic?

### What Exists

| Component | Location | Behavior |
|-----------|----------|----------|
| Explanation generator (Claude) | `src/bandit_ads/explanation_generator.py`: `ExplanationGenerator.explain_allocation_change(change_id)`, `explain_performance()`, `explain_anomaly()`, `explain_recommendation()` | Fetches change from change_tracker, builds prompt with change details, factors, MMM factors, optimizer state; can call LLM or template fallback. |
| Change tracker (allocation changes) | `src/bandit_ads/change_tracker.py`: `ChangeTracker.log_allocation_change()`, `AllocationChange` model | Stores old/new allocation, change_reason, factors, mmm_factors, optimizer_state, performance before/after. |
| Explanation on demand (MCP) | `src/bandit_ads/mcp_server_operations.py`: `explain_allocation_change(change_id)` | Calls `explanation_generator.explain_allocation_change()`; used when a client (e.g. Ask) requests an explanation for a change. |
| Orchestrator / Ask | `src/bandit_ads/orchestrator.py` (list of tools includes `explain_allocation_change`); `frontend/pages/ask.py` uses `data_service.query_orchestrator()` | Orchestrator can route to explanation tools. But `data_service.query_orchestrator()` returns `{"error": "Orchestrator API not yet implemented"}` before the real orchestrator call (dead code), so Ask effectively uses mock responses only. |
| Dashboard “latest explanation” | `frontend/services/data_service.py`: `get_latest_explanation(campaign_id)` | **Always** returns a fixed mock string (seasonality, ROAS, risk); no API call, no use of change_tracker or explanation generator. |
| Campaign detail explanation block | `frontend/pages/campaign_detail.py`: uses `data_service.get_latest_explanation(campaign_id)` | Shows the mock explanation and “Use the chat widget to ask questions!” if no explanation. |
| Optimizer API decisions | `src/bandit_ads/api/routes/optimizer.py`: `get_recent_decisions()` | Returns `[]` with TODO to integrate change tracker/explainer. |
| Optimization loop → change tracker | `src/bandit_ads/optimization_service.py`, `runner.py` | **No** call to `change_tracker.log_allocation_change()` or `log_decision()` when the bandit reallocates. So no allocation changes are logged from the real optimizer. |

### Gaps

1. **Explanations are not triggered automatically on allocation change**  
   The optimization service and runner never call `log_allocation_change()` or `log_decision()`. So when the bandit reallocates, no change record is created, and no one triggers `explain_allocation_change()`. Explanations are only generated when explicitly requested (e.g. by MCP with a change_id).

2. **Explanations are not stored and shown per decision**  
   Dashboard uses `get_latest_explanation(campaign_id)`, which is hardcoded mock data. There is no API that returns “explanation for change_id” or “last N changes with explanations,” and no automatic storage of LLM output per change (e.g. in `AllocationChange` or a linked table).

3. **Ask uses mocks, not real orchestrator**  
   `query_orchestrator()` returns the “Orchestrator API not yet implemented” error (or mock) and never hits the real orchestrator, so natural-language “why did X change?” does not use the real explanation generator or change_tracker.

4. **Content of explanations**  
   When the explainer runs, it gets real data from the change_tracker (reason, factors, MMM factors, performance). So **if** changes were logged and explanations were generated, they could reference saturation, seasonality, etc. Today they are not generated from real decisions, so the only “explanations” analysts see are generic mocks.

### Status: **Partially implemented**

- **Implemented:** Explanation generator (LLM + template), change_tracker schema and logging API, MCP explain tools, orchestrator tool list, dashboard UI that displays “an” explanation and chat.
- **Missing:** Logging every allocation change from the optimization loop; automatic trigger to generate (and optionally store) an explanation for each logged change; dashboard and API that serve stored explanations per change; wiring Ask to the real orchestrator so “why” questions use real data.

### Recommended next step (single most important)

**Log allocation changes from the optimizer and generate one explanation per change.**  
In `optimization_service._optimize_campaign()` (or in the agent/runner when allocation actually changes), after a reallocation, call `change_tracker.log_allocation_change()` with campaign_id, arm_id, old/new allocation, and whatever factors you have (e.g. from `runner.agent` and `result`). Then call `explanation_generator.explain_allocation_change(change_id)` (sync or async) and store the result (e.g. new column on `AllocationChange` or a small `decision_explanations` table). Expose “last change + explanation” (or “recent decisions with explanations”) via API and replace `get_latest_explanation()` in the frontend with that API so the dashboard shows the real “why” for the latest decision. That delivers “every decision has a plain-language explanation” and “visible alongside the decision”; making it reference saturation/seasonality/incrementality is then a matter of passing those into `log_allocation_change()` and the prompt.

---

## 4. Interface Built for Agency Analysts, Not Data Scientists

**Question:** Can an analyst see what changed, why, and what to do next without reading raw model outputs? Is the natural-language query (Ask) working in plain English? Are there UI parts that require technical knowledge to interpret or act on?

### What Exists

| Component | Location | Behavior |
|-----------|----------|----------|
| Home / dashboard | `frontend/pages/home.py` | Budget overview, channel splits, campaigns, recommendations; no raw alpha/beta or model params. |
| Campaign detail | `frontend/pages/campaign_detail.py` | KPIs, charts, channel breakdown (ROAS, allocation %), “Why These Allocations?” section, explanation card (mock), chat widget. |
| Recommendations | `frontend/pages/recommendations.py` | Pending/Applied/Rejected with title, description, explanation; Approve/Reject. Clear for analysts. |
| Incrementality dashboard | `frontend/pages/incrementality.py` | Tabs: Active Experiments, Results (lift %, iROAS, significance), Create New. “Apply to Bandit” button; some metric names (e.g. “ROAS Inflation”) are analyst-friendly. |
| Ask page | `frontend/pages/ask.py` | Natural-language input and suggested questions; calls `data_service.query_orchestrator(query, campaign_id)`. |
| Query response in Ask | `frontend/services/data_service.py`: `query_orchestrator()`, `_mock_query_response()` | With real orchestrator disabled, returns mock answers by keyword (e.g. “why” + “increase” → seasonality/ROAS explanation). So plain-English input works in a demo sense; answers are not from live data. |
| Optimizer page | `frontend/pages/optimizer.py` | Status, Pause/Resume, Force Run, “Decision Log” (empty from API), “Factor attribution” (empty). No raw priors or model params. |
| Explanation card copy | `campaign_detail.py`, `data_service.get_latest_explanation()` | Uses “Q4 Seasonality”, “ROAS Improvement”, “Risk Reduction” – analyst-oriented wording but currently mock. |

### Gaps

1. **What changed / why / what to do next**  
   “What changed” is not clearly tied to the last optimizer decision because decisions are not logged and the “latest explanation” is mock. Recommendations and incrementality results are visible, but a single “last decision + why + what to do next” summary is missing for the running optimizer.

2. **Natural-language query not backed by real system**  
   Ask accepts plain-English questions, but `query_orchestrator()` does not call the real orchestrator; it returns either an error or mock answers. So analysts cannot yet get real “why did Google Search budget increase?” or “compare Meta vs Google” from live data.

3. **Technical bits in UI**  
   Incrementality page uses terms like “ROAS Inflation”, “Incremental ROAS”, “Observed ROAS”, “p-value”, “confidence interval” – acceptable for performance analysts but may need short tooltips or a glossary. Optimizer “Decision Log” and “Factor attribution” are empty (API returns []), so they don’t expose raw model output but also don’t yet add value.

4. **Apply to Bandit**  
   “Apply to Bandit” is clear in intent, but if the campaign has no runner in memory, the apply fails with a technical error; a simple “Campaign not currently in the optimizer; start the optimizer for this campaign first” would be more analyst-friendly.

### Status: **Partially implemented**

- **Implemented:** Analyst-oriented layout (home, campaign detail, recommendations, incrementality); Ask UI and suggested questions; explanation card and “Why These Allocations?”; no exposure of alpha/beta or raw Thompson Sampling state in main flows.
- **Missing:** Reliable “what changed, why, what to do next” from real optimizer decisions and stored explanations; Ask backed by real orchestrator and live data; optional tooltips/glossary for incrementality metrics; clearer error when Apply to Bandit fails due to no runner.

### Recommended next step (single most important)

**Wire Ask to the real orchestrator and serve real “last decision + why” on the dashboard.**  
Implement the orchestrator API (or call the existing orchestrator from the frontend) so `query_orchestrator()` sends the user query and campaign context to it and returns the real answer (including explanation tools and change_tracker). Then analysts can ask in plain English and get live answers. In parallel, after you log allocation changes and store explanations (differentiator 3), add a single “Latest decision” or “What the optimizer just did” block on home or campaign detail that shows: what changed (e.g. “Google Search +20%”), the stored plain-language why, and one line of “what to do next” (e.g. “No action needed” or “Review recommendation X”). That completes the “clear summary for analysts” without requiring technical knowledge.

---

## Summary Table

| Differentiator | Status | Single most important next step |
|----------------|--------|----------------------------------|
| **1. Real-Time ML Optimization** | Partially implemented | Wire campaign runners into the loop (from DB on start/activate) and implement one end-to-end budget push (e.g. Google Ads set budget + call from apply or from `_optimize_campaign`). |
| **2. Incrementality → Bandit Automatically** | Partially implemented | After experiment completion (in `check_and_complete_expired_experiments` or equivalent), automatically call `incorporate_incrementality()` (or the apply flow) when the experiment is significant and the campaign has a runner. |
| **3. Plain-Language Explanations for Every Decision** | Partially implemented | Log every allocation change from the optimizer to the change_tracker; generate and store one explanation per change; expose “latest decision + explanation” via API and dashboard. |
| **4. Interface for Agency Analysts** | Partially implemented | Connect Ask to the real orchestrator so natural-language questions use live data; add a “Latest decision / what changed / why / what to do next” summary from real stored explanations. |

---

## File Reference Quick Map

- **Real-time optimization:** `optimization_service.py` (loop, cycle, `_optimize_campaign`, `add_campaign`, `_load_active_campaigns`); `runner.py` (setup_campaign, agent); `agent.py` (ThompsonSamplingAgent, IncrementalityAwareBandit); `api_connectors.py` (no budget set methods); `recommendations.py` (apply_recommendation TODOs); `mcp_server_operations.py` (update_campaign_budget).
- **Incrementality → bandit:** `runner.py` (IncrementalityAwareBandit default); `agent.py` (incorporate_incrementality); `api/routes/incrementality.py` (POST /apply); `incrementality_jobs.py` (check_and_complete_expired_experiments, no bandit call); `db_helpers.py` (auto_complete_experiment).
- **Explanations:** `explanation_generator.py` (explain_allocation_change, etc.); `change_tracker.py` (log_allocation_change, AllocationChange); `mcp_server_operations.py` (explain_*); `optimization_service.py` / `runner.py` (no change_tracker calls); `data_service.py` (get_latest_explanation mock); `api/routes/optimizer.py` (get_recent_decisions returns []).
- **Analyst UI:** `frontend/pages/home.py`, `campaign_detail.py`, `recommendations.py`, `incrementality.py`, `ask.py`, `optimizer.py`; `data_service.py` (query_orchestrator, get_latest_explanation).
