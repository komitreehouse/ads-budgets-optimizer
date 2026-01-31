# Phase 3: Data Pipeline - Implementation Summary

## ✅ Completed Components

### 3.1 Database Schema & Storage ✅

**Files Created:**
- `src/bandit_ads/database.py` - Database models and connection management
- `src/bandit_ads/models.py` - Pydantic models for validation
- `src/bandit_ads/db_helpers.py` - Helper functions for database operations

**Features:**
- SQLAlchemy ORM models for:
  - `Campaign` - Campaign information
  - `Arm` - Ad configuration arms
  - `Metric` - Time-series performance metrics
  - `AgentState` - Bandit agent state persistence
  - `APILog` - API call logging
- Support for SQLite (development) and PostgreSQL (production)
- Connection pooling and session management
- Database health checks

**Usage:**
```python
from src.bandit_ads.database import init_database
from src.bandit_ads.db_helpers import create_campaign, create_metric
from src.bandit_ads.models import CampaignCreate, MetricCreate

# Initialize database
db_manager = init_database(create_tables=True)

# Create campaign
campaign = create_campaign(CampaignCreate(
    name="My Campaign",
    budget=10000.0,
    start_date=datetime.utcnow()
))
```

### 3.2 Scheduled Data Collection ✅

**Files Created:**
- `src/bandit_ads/scheduler.py` - APScheduler-based job scheduling
- `src/bandit_ads/data_collector.py` - Data collection orchestration

**Features:**
- Hourly, daily, and interval-based job scheduling
- Timezone-aware scheduling
- Parallel API calls across platforms
- Rate limiting and error handling
- Automatic retry logic
- Job management (pause, resume, remove)

**Usage:**
```python
from src.bandit_ads.scheduler import get_scheduler
from src.bandit_ads.data_collector import DataCollector

# Setup scheduler
scheduler = get_scheduler(timezone='UTC')
scheduler.start()

# Add hourly data collection job
scheduler.add_hourly_job(
    func=data_collector.collect_all_active_campaigns,
    job_id='hourly_metrics_collection',
    minute=0
)
```

### 3.3 Webhook Handlers ✅

**Files Created:**
- `src/bandit_ads/webhooks.py` - Webhook server and handlers

**Features:**
- Flask-based webhook server
- Platform-specific handlers:
  - Google Ads webhooks
  - Meta Ads webhooks
  - The Trade Desk webhooks
- Signature verification for security
- Real-time metric updates
- Health check endpoint

**Usage:**
```python
from src.bandit_ads.webhooks import run_webhook_server

# Start webhook server
run_webhook_server(host='0.0.0.0', port=5000)
```

**Endpoints:**
- `POST /webhook/google` - Google Ads webhooks
- `POST /webhook/meta` - Meta Ads webhooks
- `POST /webhook/trade_desk` - The Trade Desk webhooks
- `GET /webhook/health` - Health check

### 3.4 Data Validation & Quality ✅

**Files Created:**
- `src/bandit_ads/data_validator.py` - Data validation and anomaly detection

**Features:**
- Pre-storage validation (required fields, logical constraints)
- Anomaly detection using statistical methods (Z-score)
- Data quality scoring:
  - Completeness score
  - Timeliness score
  - Consistency score
- Automatic data cleaning

**Usage:**
```python
from src.bandit_ads.data_validator import DataValidator, validate_and_clean_metric

validator = DataValidator(anomaly_threshold=3.0)
is_valid, cleaned_metric, warnings = validate_and_clean_metric(metric_data, validator)

# Detect anomalies
anomalies = validator.detect_anomalies(arm_id, new_metric, lookback_days=7)
```

## 📋 Next Steps (Remaining Components)

### 3.5 ETL Pipeline for MMM Analysis (Pending)
- Extract data from database
- Transform for MMM modeling
- Calculate derived metrics
- Update MMM coefficients
- Load processed data

### 3.6 Pipeline Orchestration (Pending)
- Workflow definitions
- Job dependencies
- Pipeline monitoring
- Health checks and alerting

## 🔧 Installation

**New Dependencies Added:**
```bash
pip install sqlalchemy==2.0.23
pip install apscheduler==3.10.4
pip install flask==3.0.0
pip install pydantic==2.5.0
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

## 🚀 Quick Start

### 1. Initialize Database

```python
from src.bandit_ads.database import init_database

# Initialize SQLite database (default)
db_manager = init_database(create_tables=True)

# Or use PostgreSQL
db_manager = init_database(
    database_url='postgresql://user:pass@localhost/bandit_ads',
    create_tables=True
)
```

### 2. Setup Scheduled Data Collection

```python
from src.bandit_ads.scheduler import get_scheduler
from src.bandit_ads.data_collector import create_data_collector_from_config
from src.bandit_ads.utils import ConfigManager

# Load config
config_manager = ConfigManager('config.yaml')
config = config_manager.to_dict()

# Create data collector
data_collector = create_data_collector_from_config(config)

# Setup scheduler
scheduler = get_scheduler(timezone='UTC')
scheduler.start()

# Add hourly collection job
scheduler.add_hourly_job(
    func=data_collector.collect_all_active_campaigns,
    job_id='hourly_collection',
    minute=0
)
```

### 3. Start Webhook Server

```python
from src.bandit_ads.webhooks import run_webhook_server

# Configure webhook secrets (optional but recommended)
from src.bandit_ads.webhooks import get_webhook_handler
handler = get_webhook_handler(secret_keys={
    'google': 'your_google_secret',
    'meta': 'your_meta_secret',
    'trade_desk': 'your_ttd_secret'
})

# Start server
run_webhook_server(host='0.0.0.0', port=5000)
```

## 📊 Database Schema

### Tables

1. **campaigns**
   - id, name, budget, start_date, end_date, status, created_at, updated_at

2. **arms**
   - id, campaign_id, platform, channel, creative, bid, created_at

3. **metrics**
   - id, campaign_id, arm_id, timestamp, impressions, clicks, conversions,
     revenue, cost, roas, ctr, cvr, source, created_at

4. **agent_states**
   - id, campaign_id, arm_id, alpha, beta, spending, impressions, rewards,
     reward_variance, trials, risk_score, contextual_state, last_updated

5. **api_logs**
   - id, platform, endpoint, method, status_code, response_time, success,
     error_message, request_data, response_data, timestamp

## 🔍 Data Flow

```
API Connectors → Data Collector → Validator → Database
                                    ↓
                              Anomaly Detection
                                    ↓
                              Quality Scoring
```

## ⚠️ Notes

1. **Dependencies**: Make sure to install new dependencies before using Phase 3 features
2. **Database**: SQLite is used by default (good for development). Use PostgreSQL for production
3. **Webhooks**: Configure webhook secrets in your platform settings for security
4. **Scheduler**: The scheduler runs in a background thread. Make sure your main process stays alive
5. **Error Handling**: All components include comprehensive error handling and logging

## 🧪 Testing

To test the database:
```python
from src.bandit_ads.database import init_database
from src.bandit_ads.db_helpers import create_campaign
from src.bandit_ads.models import CampaignCreate
from datetime import datetime

db_manager = init_database(create_tables=True)
campaign = create_campaign(CampaignCreate(
    name="Test Campaign",
    budget=1000.0,
    start_date=datetime.utcnow()
))
print(f"Created campaign: {campaign.name} (ID: {campaign.id})")
```

## 📝 Configuration

Add to `config.yaml`:
```yaml
database:
  url: "sqlite:///data/bandit_ads.db"  # or PostgreSQL URL
  pool_size: 10

scheduler:
  timezone: "UTC"
  jobs:
    hourly_collection:
      type: hourly
      minute: 0
    daily_aggregation:
      type: daily
      hour: 0
      minute: 0

webhooks:
  host: "0.0.0.0"
  port: 5000
  secret_keys:
    google: ""  # Set in environment variables
    meta: ""
    trade_desk: ""
```

### 3.5 ETL Pipeline for MMM Analysis ✅

**Files Created:**
- `src/bandit_ads/etl.py` - ETL pipeline implementation

**Features:**
- Extract: Pull data from database for campaigns
- Transform: Calculate aggregated metrics, time-series features, MMM features
- Load: Update MMM coefficients in data loader
- Seasonality detection
- Trend analysis
- Variance calculations

**Usage:**
```python
from src.bandit_ads.etl import ETLPipeline

etl = ETLPipeline(lookback_days=30)
result = etl.run_etl_pipeline(campaign_id=1)

# Or run for all campaigns
results = etl.run_etl_for_all_campaigns()
```

### 3.6 Pipeline Orchestration ✅

**Files Created:**
- `src/bandit_ads/pipeline.py` - Pipeline orchestration and monitoring

**Features:**
- Workflow definitions and execution
- Job dependencies management
- Pipeline health monitoring
- Performance metrics
- Scheduled workflow execution
- Error handling and recovery

**Usage:**
```python
from src.bandit_ads.pipeline import create_pipeline_manager
from src.bandit_ads.utils import ConfigManager

config_manager = ConfigManager('config.yaml')
manager = create_pipeline_manager(config_manager)

# Get health status
health = manager.get_pipeline_health()

# Run workflow manually
result = manager.run_workflow('daily')

# Get metrics
metrics = manager.get_pipeline_metrics()
```

## ✅ Status

- ✅ Database schema and models
- ✅ Database helper functions
- ✅ Scheduled data collection
- ✅ Data collector service
- ✅ Webhook handlers
- ✅ Data validation and quality checks
- ✅ ETL pipeline for MMM analysis
- ✅ Pipeline orchestration and monitoring

**Phase 3 Progress: 100% Complete! 🎉**
