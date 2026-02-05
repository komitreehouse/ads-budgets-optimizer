# Campaign Settings Implementation

## Overview

Campaign settings are now stored in the database, allowing users to:
1. Configure targets and benchmarks per campaign
2. Adjust status indicator thresholds
3. Save primary KPI preference
4. All settings persist across sessions

## Database Changes

### New Campaign Fields

Added to `Campaign` model:
- `primary_kpi` (TEXT, default: "ROAS") - User's preferred primary KPI
- `target_roas`, `target_cpa`, `target_revenue`, `target_conversions` - Campaign targets
- `benchmark_roas`, `benchmark_cpa`, `benchmark_revenue`, `benchmark_conversions` - Industry/account benchmarks
- `scaling_threshold` (REAL, default: 1.1) - Multiplier for "scaling" status (10% above target)
- `stable_threshold` (REAL, default: 0.9) - Multiplier for "stable" status (10% below target)

## Migration

Run the migration script to add new columns:

```bash
python scripts/migrate_database.py
```

This will:
- Add `platform_entity_ids` to arms table (if not exists)
- Add all campaign settings columns (if not exist)
- Preserve existing data

## API Endpoints

### GET `/api/campaigns/{id}/settings`
Returns campaign settings including:
- Primary KPI
- Targets (ROAS, CPA, Revenue, Conversions)
- Benchmarks
- Thresholds

### PUT `/api/campaigns/{id}/settings`
Updates campaign settings. Accepts:
```json
{
  "primary_kpi": "ROAS",
  "targets": {
    "roas": 2.0,
    "cpa": 50.0,
    "revenue": 30000.0,
    "conversions": 100
  },
  "benchmarks": {
    "roas": 1.8,
    "cpa": 55.0,
    "revenue": 27000.0,
    "conversions": 90
  },
  "thresholds": {
    "scaling": 1.1,
    "stable": 0.9
  }
}
```

## Frontend Features

### Primary KPI Selector
- Dropdown to select ROAS, CPA, Revenue, or Conversions
- Preference is saved to database when changed
- Loads saved preference on page load
- Falls back to campaign default if no preference saved

### Settings Panel
Accessible via "⚙️ Settings" button next to KPI selector.

**Targets Section:**
- Target ROAS
- Target CPA ($)
- Target Revenue ($)
- Target Conversions

**Benchmarks Section:**
- Benchmark ROAS
- Benchmark CPA ($)
- Benchmark Revenue ($)
- Benchmark Conversions

**Status Thresholds:**
- Scaling Threshold (default: 1.1 = 10% above target)
- Stable Threshold (default: 0.9 = 10% below target)

### Status Indicator Logic

Uses configurable thresholds:
- **🟢 Scaling:** Primary KPI ≥ target × scaling_threshold
- **🟡 Stable:** Primary KPI between target × stable_threshold and target × scaling_threshold
- **🔴 Underperforming:** Primary KPI < target × stable_threshold

## Default Values

If no settings are configured, defaults are used:

**Targets:**
- ROAS: 2.0
- CPA: $50
- Revenue: 2x campaign budget
- Conversions: 100

**Benchmarks:**
- ROAS: 1.8
- CPA: $55
- Revenue: 1.8x campaign budget
- Conversions: 90

**Thresholds:**
- Scaling: 1.1 (10% above target)
- Stable: 0.9 (10% below target)

## Usage

1. **Set Primary KPI:**
   - Select from dropdown
   - Automatically saved to database

2. **Configure Settings:**
   - Click "⚙️ Settings" button
   - Adjust targets, benchmarks, and thresholds
   - Click "💾 Save Settings"
   - Settings persist across sessions

3. **View Status:**
   - Status indicator updates based on:
     - Current performance vs target
     - Configured thresholds
     - Selected primary KPI

## Data Service Methods

### `get_campaign_settings(campaign_id)`
Returns campaign settings from API or mock data.

### `update_campaign_settings(campaign_id, settings)`
Updates campaign settings via API.

## Notes

- Settings are per-campaign (not global)
- Primary KPI preference is saved immediately on change
- Other settings require clicking "Save Settings"
- Thresholds are multipliers (not percentages)
- Revenue targets can be null (will use budget-based calculation)
