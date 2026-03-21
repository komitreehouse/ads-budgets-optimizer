# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IPSA (Intelligent Platform for Strategic Advertising) — an advertising budget optimization platform using multi-armed bandits, media mix modeling (MMM), and LLM-powered interpretability. FastAPI backend, Streamlit frontend, SQLite/PostgreSQL database.

## Common Commands

### Setup
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/migrate_database.py
python scripts/create_sample_data.py  # optional sample data
```

### Run the Application
```bash
# API server (Terminal 1) - serves on http://localhost:8000
python scripts/run_api.py
python scripts/run_api.py --reload  # with auto-reload

# Frontend (Terminal 2) - serves on http://localhost:8501
python scripts/start_frontend.py
# or: streamlit run frontend/app.py
```

### Tests
```bash
pytest tests/                          # all tests
pytest tests/test_agent.py             # single test file
pytest --cov=src/bandit_ads tests/     # with coverage
python scripts/test_api.py             # API endpoint smoke tests
```

### Run Simulations
```bash
python scripts/run_simulation.py
python scripts/run_contextual_example.py
```

## Architecture

### Core Package (`src/bandit_ads/`)

**Optimization Engine:**
- `agent.py` — Thompson Sampling bandit (Beta distribution-based)
- `contextual_agent.py` — LinUCB contextual bandit with feature support
- `arms.py` — Arm definitions (platform, channel, creative, bid combinations)
- `env.py` — Simulated ad environment; `realtime_env.py` — live API environment
- `runner.py` — `AdOptimizationRunner` orchestrates campaign optimization rounds

**Data Layer:**
- `database.py` — SQLAlchemy models: Campaign, Arm, Metric, AgentState, APILog, IncrementalityExperiment/Metric
- `models.py` — Pydantic validation models
- `data_loader.py` — MMMDataLoader for historical data; `etl.py` — ETL pipeline
- `data_validator.py` — Data validation

**API (`src/bandit_ads/api/`):**
- `main.py` — FastAPI app with CORS, global error handling
- Routes: `campaigns.py`, `dashboard.py`, `recommendations.py`, `optimizer.py`, `incrementality.py`
- Health check at `/api/health`; API docs at `/docs`

**Interpretability / LLM Layer:**
- `explanation_generator.py` — Claude API for human-readable optimization explanations
- `llm_router.py` — Routes between LLM providers (Anthropic, OpenAI)
- `vector_store.py` — ChromaDB RAG context store

**Integrations:**
- `api_connectors.py` — Google Ads, Meta/Facebook Ads, Trade Desk connectors
- `incrementality.py` — Experiment design with holdout groups
- `scheduler.py` — APScheduler background jobs

### Frontend (`frontend/`)

- `app.py` — Main Streamlit app (IPSA branding, terracotta/gold theme)
- `components/` — Reusable UI components
- `pages/` — Streamlit page-based routing
- `services/data_service.py` — `DataService` class abstracts API calls with mock data fallback

### Key Patterns

- **Database access:** `DatabaseManager` with context manager (`with db_manager.get_session() as session:`)
- **Frontend data:** `DataService` tries the API first, falls back to mock data if unavailable
- **Configuration:** `config.example.yaml` (copy to `config.yaml`); supports `.env` via python-dotenv
- **API credentials:** Configured in config.yaml under api_credentials section (Google Ads, Meta, Trade Desk)

## Database

SQLite at `data/bandit_ads.db` (dev). PostgreSQL supported for production. Schema managed via `scripts/migrate_database.py`.
