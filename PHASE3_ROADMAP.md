# Phase 3: Data Pipeline - Implementation Roadmap

## Overview
Phase 3 focuses on building a robust data pipeline for:
- Scheduled data collection from APIs
- Webhook handlers for real-time events
- Database storage for historical data
- Data validation and quality checks
- ETL processes for MMM analysis

---

## Phase 3.1: Database Schema & Storage (Week 1)

### 3.1.1 Database Models
**Goal:** Design and implement database schema for storing campaign data

**Steps:**
1. **Create database models** (`src/bandit_ads/database.py`)
   - Campaigns table
   - Arms table
   - Performance metrics table (time-series)
   - Agent state table (for persistence)
   - API call logs table

2. **Database abstraction layer**
   - Support for SQLite (development) and PostgreSQL (production)
   - Connection pooling
   - Migration support

3. **Data models:**
   ```python
   - Campaign: id, name, budget, start_date, end_date, status
   - Arm: id, campaign_id, platform, channel, creative, bid
   - Metrics: id, arm_id, timestamp, impressions, clicks, conversions, cost, revenue, roas
   - AgentState: campaign_id, arm_id, alpha, beta, spending, trials, last_updated
   - APILog: id, platform, endpoint, status, response_time, error_message, timestamp
   ```

**Deliverables:**
- `src/bandit_ads/database.py` - Database models and connection management
- `src/bandit_ads/models.py` - SQLAlchemy models (or similar)
- Migration scripts

---

## Phase 3.2: Scheduled Data Collection (Week 1-2)

### 3.2.1 Data Scheduler
**Goal:** Automatically pull data from APIs on a schedule

**Steps:**
1. **Create scheduler module** (`src/bandit_ads/scheduler.py`)
   - Use `schedule` or `APScheduler` library
   - Configurable intervals (hourly, daily, etc.)
   - Timezone-aware scheduling

2. **Data collection jobs:**
   - Hourly metrics pull from all connected APIs
   - Daily aggregation jobs
   - Weekly MMM coefficient updates

3. **Job management:**
   - Job status tracking
   - Retry failed jobs
   - Job history logging

**Deliverables:**
- `src/bandit_ads/scheduler.py` - Scheduler implementation
- Configuration for job intervals
- Job monitoring and logging

### 3.2.2 Data Collection Service
**Goal:** Service to orchestrate data pulls from multiple APIs

**Steps:**
1. **Create data collection service** (`src/bandit_ads/data_collector.py`)
   - Coordinate API calls across platforms
   - Handle rate limiting
   - Aggregate metrics by arm
   - Store in database

2. **Features:**
   - Parallel API calls (where possible)
   - Incremental updates (only fetch new data)
   - Data deduplication
   - Error recovery

**Deliverables:**
- `src/bandit_ads/data_collector.py` - Data collection orchestration
- Integration with existing API connectors
- Database storage integration

---

## Phase 3.3: Webhook Handlers (Week 2)

### 3.3.1 Webhook Infrastructure
**Goal:** Receive real-time events from advertising platforms

**Steps:**
1. **Webhook server** (`src/bandit_ads/webhooks.py`)
   - Flask/FastAPI endpoint for receiving webhooks
   - Signature verification for security
   - Event routing

2. **Platform-specific handlers:**
   - Google Ads conversion webhooks
   - Meta Ads conversion events
   - The Trade Desk event callbacks

3. **Event processing:**
   - Parse webhook payloads
   - Map to internal arm structure
   - Update metrics in real-time
   - Trigger agent updates

**Deliverables:**
- `src/bandit_ads/webhooks.py` - Webhook server and handlers
- Webhook endpoint configuration
- Security (authentication, signature verification)

---

## Phase 3.4: Data Validation & Quality (Week 2-3)

### 3.4.1 Data Validation Layer
**Goal:** Ensure data quality before storage

**Steps:**
1. **Validation rules:**
   - Check for missing required fields
   - Validate data types and ranges
   - Detect anomalies (spikes, drops)
   - Cross-platform consistency checks

2. **Data quality metrics:**
   - Completeness score
   - Timeliness score
   - Accuracy checks

3. **Anomaly detection:**
   - Statistical outlier detection
   - Trend analysis
   - Alert on suspicious data

**Deliverables:**
- `src/bandit_ads/data_validator.py` - Validation logic
- Anomaly detection algorithms
- Quality reporting

### 3.4.2 Data Cleaning
**Goal:** Clean and normalize data before use

**Steps:**
1. **Data cleaning functions:**
   - Handle missing values
   - Normalize platform-specific formats
   - Deduplicate records
   - Handle timezone conversions

2. **Data transformation:**
   - Standardize metric names
   - Convert currencies
   - Normalize date formats

**Deliverables:**
- Data cleaning utilities
- Transformation pipelines

---

## Phase 3.5: ETL for MMM Analysis (Week 3)

### 3.5.1 ETL Pipeline
**Goal:** Extract, Transform, Load data for MMM modeling

**Steps:**
1. **Extract:**
   - Pull from database
   - Aggregate by time periods
   - Filter by date ranges

2. **Transform:**
   - Calculate derived metrics (CTR, CVR, ROAS)
   - Apply MMM factors
   - Create time-series features
   - Handle seasonality

3. **Load:**
   - Store processed data
   - Update MMM coefficients
   - Feed to bandit agent

**Deliverables:**
- `src/bandit_ads/etl.py` - ETL pipeline
- MMM feature engineering
- Automated coefficient updates

---

## Phase 3.6: Data Pipeline Orchestration (Week 3-4)

### 3.6.1 Pipeline Manager
**Goal:** Orchestrate all data pipeline components

**Steps:**
1. **Pipeline orchestration:**
   - Define pipeline workflows
   - Handle dependencies between jobs
   - Monitor pipeline health
   - Alert on failures

2. **Workflow examples:**
   - Daily: Collect data → Validate → Store → Update MMM → Refresh agent
   - Hourly: Collect data → Validate → Store
   - Real-time: Webhook → Validate → Store → Update agent

**Deliverables:**
- `src/bandit_ads/pipeline.py` - Pipeline orchestration
- Workflow definitions
- Monitoring dashboard

---

## Implementation Order

### Week 1: Foundation
1. ✅ Database schema design
2. ✅ Database models implementation
3. ✅ Basic data storage functions
4. ✅ Data collection service skeleton

### Week 2: Collection & Webhooks
1. ✅ Scheduler implementation
2. ✅ Scheduled data pulls
3. ✅ Webhook server setup
4. ✅ Webhook handlers for major platforms

### Week 3: Quality & ETL
1. ✅ Data validation layer
2. ✅ Anomaly detection
3. ✅ ETL pipeline for MMM
4. ✅ Data quality monitoring

### Week 4: Integration & Testing
1. ✅ Pipeline orchestration
2. ✅ End-to-end testing
3. ✅ Performance optimization
4. ✅ Documentation

---

## Technical Requirements

### Dependencies to Add:
```python
# Database
sqlalchemy==2.0.0
alembic==1.13.0  # For migrations
psycopg2-binary==2.9.9  # PostgreSQL adapter

# Scheduling
APScheduler==3.10.4
schedule==1.2.0

# Webhooks
flask==3.0.0  # or FastAPI
flask-cors==4.0.0

# Data processing
pandas==2.3.3  # Already have
numpy==2.0.2  # Already have
```

### Database Options:
- **Development:** SQLite (no setup required)
- **Production:** PostgreSQL (recommended) or MySQL

---

## Configuration Updates

### Add to `config.example.yaml`:
```yaml
database:
  type: sqlite  # or postgresql
  connection_string: "sqlite:///bandit_ads.db"
  # For PostgreSQL:
  # connection_string: "postgresql://user:pass@localhost/bandit_ads"

scheduler:
  enabled: true
  timezone: "America/New_York"
  jobs:
    hourly_metrics:
      enabled: true
      interval: 3600  # seconds
    daily_aggregation:
      enabled: true
      time: "02:00"  # 2 AM daily

webhooks:
  enabled: true
  port: 8080
  secret_key: ""  # For signature verification
  endpoints:
    google: "/webhooks/google"
    meta: "/webhooks/meta"
    trade_desk: "/webhooks/trade_desk"

data_quality:
  validation_enabled: true
  anomaly_detection: true
  alert_threshold: 0.1  # Alert if >10% data quality issues
```

---

## Success Criteria

Phase 3 is complete when:
- ✅ Data is automatically collected from APIs on schedule
- ✅ Webhooks receive and process real-time events
- ✅ All data is stored in database with proper schema
- ✅ Data validation catches errors before storage
- ✅ ETL pipeline updates MMM coefficients automatically
- ✅ Pipeline monitoring shows health status
- ✅ Historical data can be queried for analysis

---

## Next Steps After Phase 3

**Phase 4: Dashboard/UI**
- Real-time monitoring dashboard
- Performance visualization
- Campaign management interface

**Phase 5: Advanced Features**
- Contextual bandits
- Multi-objective optimization
- A/B testing framework

---

**Estimated Timeline:** 3-4 weeks
**Priority:** High (enables production use with real data)
