# Campaign Detail Page Enhancements

## Overview

The campaign detail page has been completely redesigned with comprehensive real-time metrics, advanced visualizations, and actionable insights.

## ✅ Implemented Features

### 1. Core KPIs Section (Current vs Target)

**Location:** Top of page, immediately after header

**Features:**
- **Spend Metrics:**
  - Today's spend vs daily target
  - MTD spend vs monthly target
  - Total spend vs campaign budget
  
- **Primary KPI (Selectable):**
  - ROAS, CPA, Revenue, or Conversions
  - Current value vs target
  - Efficiency delta vs benchmark (%)
  
- **Status Indicators:**
  - 🟢 Scaling opportunity (performing >10% above target)
  - 🟡 Stable / watch (within ±10% of target)
  - 🔴 Underperforming (<10% below target)
  
- **Secondary KPIs:**
  - CPC (Cost Per Click)
  - CVR (Conversion Rate)
  - AOV (Average Order Value)

### 2. Spend & KPI Over Time (Dual-Axis Chart)

**Location:** Below Core KPIs section

**Features:**
- **Dual-axis visualization:**
  - Left Y-axis: Spend ($)
  - Right Y-axis: Primary KPI (ROAS, CPA, Revenue, or Conversions)
  - X-axis: Time (dates)

- **Advanced Controls:**
  - Time range selector (7D, 30D, 90D, MTD, QTD)
  - Rolling average toggle (7-day window)
  - Anomaly detection toggle

- **Anomaly Detection:**
  - Automatic detection of spend spikes (2+ standard deviations)
  - Automatic detection of KPI drops (2+ standard deviations)
  - Visual markers on chart (triangles)

- **Future Enhancements Ready:**
  - Shaded learning/test periods (structure in place)
  - Custom rolling window sizes

### 3. Channel & Tactic Breakdown

**Location:** Below Spend & KPI chart

**Features:**
- **Summary Metrics:**
  - Total channels
  - Average ROAS across channels
  - Average pacing
  - Total budget utilization

- **Detailed Table:**
  - Channel name and platform
  - Spend and revenue
  - ROAS
  - Budget allocation %
  - Pacing % (vs expected spend)
  - Status indicator (🟢 on pace, 🟡 behind, 🔴 significantly behind)

- **Expandable Details:**
  - Performance metrics per channel
  - Budget utilization breakdown
  - Individual arms within each channel
  - Creative and bid details

### 4. Chat Widget for Explanations

**Location:** 
- Button in header (top right)
- Expandable panel at bottom of page

**Features:**
- Ask questions about campaign performance
- Get explanations for allocations
- View conversation history (last 5 messages)
- Context-aware (knows which campaign)

**Status:** UI complete, ready for orchestrator API integration

### 5. Audience / Geo / Creative Insights

**Location:** Below Channel Breakdown

**Features:**
- **Top Audiences:** Performance by audience segment
- **Top Geos:** Performance by geographic region
- **Top Creatives:** Performance by creative variant

**Status:** Placeholder structure in place, ready for MMM-lite data integration

### 6. Explanation Section

**Location:** Bottom of page

**Features:**
- Latest optimizer explanation
- Contributing factors
- Timestamp and model information
- Integration with chat widget

## API Endpoints Added

### `/api/campaigns/{id}/enhanced-metrics`
- Returns today/MTD/total metrics
- Includes targets and benchmarks
- Calculates efficiency delta
- Determines status (scaling/stable/underperforming)

**Query Parameters:**
- `primary_kpi`: ROAS, CPA, Revenue, or Conversions

### `/api/campaigns/{id}/channel-breakdown`
- Returns channel and tactic breakdown
- Includes budget utilization and pacing
- Groups arms by channel
- Calculates performance metrics per channel

## Components Created

### `frontend/components/dual_axis_chart.py`
- Dual-axis chart rendering
- Rolling average calculation
- Anomaly detection algorithm
- Learning period visualization (ready)

### `frontend/components/chat_widget.py`
- Reusable chat widget component
- Message history management
- Context-aware queries

## Data Service Methods Added

### `get_enhanced_campaign_metrics(campaign_id, primary_kpi)`
- Fetches enhanced metrics from API
- Falls back to mock data if API unavailable

### `get_channel_breakdown(campaign_id)`
- Fetches channel breakdown from API
- Falls back to mock data if API unavailable

## Default Targets & Benchmarks

Currently using configurable defaults (can be moved to database):

**Targets:**
- ROAS: 2.0
- CPA: $50
- Revenue: 2x campaign budget
- Conversions: 100

**Benchmarks:**
- ROAS: 1.8 (industry average)
- CPA: $55
- Revenue: 1.8x campaign budget
- Conversions: 90

## Status Indicator Logic

- **🟢 Scaling:** Primary KPI ≥ target × 1.1
- **🟡 Stable:** Primary KPI between target × 0.9 and target × 1.1
- **🔴 Underperforming:** Primary KPI < target × 0.9

## Next Steps / Future Enhancements

1. **Targets & Benchmarks:**
   - Add to Campaign database model
   - Allow per-campaign configuration
   - Industry-specific defaults

2. **Learning Period Detection:**
   - Automatically detect test/learning periods
   - Shade periods on chart
   - Exclude from performance calculations

3. **MMM-Lite Integration:**
   - Connect to MMM analysis results
   - Populate Audience/Geo/Creative insights
   - Add incrementality estimates

4. **Orchestrator Integration:**
   - Connect chat widget to orchestrator API
   - Enable natural language queries
   - Generate explanations on demand

5. **Anomaly Explanations:**
   - Auto-generate explanations for detected anomalies
   - Link to chat widget
   - Suggest actions

6. **Export Functionality:**
   - Export charts as images
   - Export data as CSV
   - Generate PDF reports

## Testing

To test the enhanced campaign detail page:

1. Start the API server:
   ```bash
   source .venv/bin/activate
   python scripts/run_api.py
   ```

2. Start the frontend:
   ```bash
   streamlit run frontend/app.py
   ```

3. Navigate to a campaign detail page
4. Test all features:
   - Change primary KPI selector
   - Toggle rolling average
   - Toggle anomaly detection
   - Expand channel breakdowns
   - Use chat widget

## Notes

- All features work with both real API data and mock data
- Mock data provides realistic examples for testing
- Status indicators use configurable thresholds
- Chart components are reusable across the application
- Chat widget can be added to other pages easily
