# Testing Guide

This guide explains how to test and verify the ads budget optimizer system.

## Quick Test

Run the comprehensive test suite:

```bash
python scripts/test_simulation.py
```

This will run 5 tests:
1. Basic Thompson Sampling bandit
2. Contextual bandit with demographics & time-of-day
3. Full campaign runner (standard mode)
4. Full campaign runner (contextual mode)
5. Historical data loading

## Mock Data Files

### JSON Format (`data/mock_historical_data.json`)

Contains historical performance data in JSON format:

```json
{
  "historical_performance": {
    "Google_Search_Creative A_1.0": {
      "historical_ctr": 0.085,
      "historical_cvr": 0.142,
      "historical_roas": 1.65,
      "spend_baseline": 5000.0,
      "variance_ctr": 0.0012,
      "variance_cvr": 0.0035
    }
  },
  "seasonal_multipliers": { ... }
}
```

### CSV Format (`data/mock_historical_data.csv`)

Contains historical performance data in CSV format:

```csv
platform,channel,creative,bid,date,impressions,clicks,conversions,revenue,cost,ctr,cvr,roas
Google,Search,Creative A,1.0,2024-01-15,5000,425,60,900,382,0.085,0.141,2.36
```

## Using Mock Data

### Option 1: Load from JSON File

```python
from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config

config = create_sample_campaign_config()
config['historical_data'] = {
    'enabled': True,
    'file_path': 'data/mock_historical_data.json'
}

runner = AdOptimizationRunner(config)
runner.setup_campaign()
results = runner.run_campaign(max_rounds=100)
```

### Option 2: Load from CSV File

```python
config['historical_data'] = {
    'enabled': True,
    'file_path': 'data/mock_historical_data.csv'
}
```

### Option 3: Create Programmatically

```python
from src.bandit_ads.data_loader import MMMDataLoader

loader = MMMDataLoader()
custom_data = {
    'historical_performance': {
        'Google_Search_Creative A_1.0': {
            'historical_ctr': 0.09,
            'historical_cvr': 0.16,
            'historical_roas': 1.75,
            'spend_baseline': 5000.0,
            'variance_ctr': 0.001,
            'variance_cvr': 0.003
        }
    }
}
loader.load_historical_data(data_dict=custom_data)
```

## Example Scripts

### Basic Simulation

```bash
python scripts/run_simulation.py
```

### Contextual Bandit Example

```bash
python scripts/run_contextual_example.py
```

### Load Mock Data Example

```bash
python scripts/load_mock_data_example.py
```

## Test Scenarios

### Test 1: Basic Bandit
- Tests standard Thompson Sampling without context
- Verifies arm selection and budget allocation
- Checks ROAS optimization

### Test 2: Contextual Bandit
- Tests contextual bandit with user demographics
- Simulates different user contexts (age, gender, device, time)
- Verifies context-aware arm selection

### Test 3: Full Campaign (Standard)
- Tests complete campaign runner
- Uses sample campaign configuration
- Verifies MMM factors integration

### Test 4: Full Campaign (Contextual)
- Tests complete campaign runner with contextual bandit
- Verifies context generation and usage
- Checks contextual performance tracking

### Test 5: Historical Data Loading
- Tests loading historical data from JSON/CSV
- Verifies prior initialization
- Checks data processing

## Expected Output

When tests pass, you should see:

```
✅ Test 1 Complete:
   Total Spent: $116.40
   Overall ROAS: 1.014
   Budget Utilization: 23.3%

✅ Test 2 Complete:
   Total Spent: $104.00
   Overall ROAS: 1.346
   Feature Dimension: 46

✅ Test 3 Complete:
   Total Rounds: 30
   Performance Log Entries: 3

✅ Test 4 Complete:
   Total Rounds: 30
   Using Contextual Bandit: True

✅ Test 5 Complete:
   Priors for Arm(...):
     Historical CTR: 0.085
     Historical CVR: 0.142
     Historical ROAS: 1.65

✅ ALL TESTS COMPLETED SUCCESSFULLY!
```

## Troubleshooting

### Issue: "No module named 'src'"
**Solution**: Make sure you're running from the project root directory.

### Issue: "Config file not found"
**Solution**: The system will use defaults if config file is missing. This is fine for testing.

### Issue: "Historical data not loading"
**Solution**: 
- Check file paths are relative to project root
- Verify JSON/CSV format matches expected structure
- Check file permissions

### Issue: "Contextual bandit not working"
**Solution**:
- Verify `contextual.enabled: true` in config
- Check that context is being passed to `select_arm()` and `update()`
- Ensure context features are configured correctly

## Creating Your Own Test Data

### JSON Format

```json
{
  "historical_performance": {
    "Platform_Channel_Creative_Bid": {
      "historical_ctr": 0.05,
      "historical_cvr": 0.10,
      "historical_roas": 1.5,
      "spend_baseline": 1000.0,
      "variance_ctr": 0.001,
      "variance_cvr": 0.003
    }
  }
}
```

### CSV Format

Required columns:
- `platform`, `channel`, `creative`, `bid`
- `ctr`, `cvr`, `roas` (or `impressions`, `clicks`, `conversions`, `revenue`, `cost`)

Optional columns:
- `date`, `spend`

## Next Steps

After verifying tests pass:
1. Customize mock data with your own historical performance
2. Configure your campaign parameters
3. Run full campaigns with your data
4. Analyze results and optimize

For more details, see:
- `README.md` - General usage
- `CONTEXTUAL_BANDITS.md` - Contextual bandit details
- `IMPLEMENTATION_SUMMARY.md` - Implementation details
