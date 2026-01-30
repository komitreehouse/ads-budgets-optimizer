# Contextual Bandits Feature

## Overview

The contextual bandit feature provides an **optional** enhancement to the standard multi-armed bandit system. It allows the agent to learn arm performance conditioned on contextual features such as user demographics, time-of-day, device type, and custom features.

## Key Benefits

1. **More Granular Optimization**: Learn that "Google Search works better for 25-34 age group in the evening"
2. **Better Budget Allocation**: Allocate budget based on both arm attributes and user context
3. **Temporal Adaptation**: Automatically adapt to time-of-day and day-of-week patterns
4. **Customizable**: Add your own contextual features (user segments, purchase history, etc.)

## Architecture

### Components

1. **`ContextFeatureExtractor`** (`context_features.py`):
   - Extracts and encodes contextual features
   - Supports demographics, temporal, device, and custom features
   - One-hot encodes categorical features
   - Returns feature vectors for learning

2. **`ContextualBanditAgent`** (`contextual_agent.py`):
   - Extends `ThompsonSamplingAgent`
   - Uses linear model (LinUCB-style) to learn context-arm interactions
   - Each arm has: `reward = context^T * theta_arm`
   - Falls back to standard Thompson Sampling when context is not provided

3. **Updated `AdOptimizationRunner`**:
   - Automatically detects contextual mode from config
   - Generates context for each round (in simulation)
   - Passes context to agent and environment

## Usage

### Basic Configuration

Enable contextual bandits in your config file:

```yaml
contextual:
  enabled: true
  alpha: 1.0  # Exploration parameter
  features:
    demographics:
      age_group: true
      gender: true
      location: true
    temporal:
      hour: true
      day_of_week: true
      month: true
      is_weekend: true
    device:
      device_type: true
      os: false
    custom: {}
```

### Programmatic Usage

```python
from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config

# Create config
config = create_sample_campaign_config()
config['contextual'] = {
    'enabled': True,
    'features': {
        'demographics': {'age_group': True, 'gender': True},
        'temporal': {'hour': True, 'day_of_week': True}
    }
}

# Run campaign
runner = AdOptimizationRunner(config)
runner.setup_campaign()
results = runner.run_campaign(max_rounds=100)
```

### Example Script

```bash
python scripts/run_contextual_example.py
```

## Supported Features

### Demographics
- **Age Group**: 18-24, 25-34, 35-44, 45-54, 55+ (one-hot encoded)
- **Gender**: Male, Female, Other (one-hot encoded)
- **Location**: US, EU, Asia, Other (one-hot encoded)

### Temporal
- **Hour**: 0-23 (one-hot encoded, 24 features)
- **Day of Week**: Monday-Sunday (one-hot encoded, 7 features)
- **Month**: January-December (one-hot encoded, 12 features)
- **Is Weekend**: Binary (1 if Saturday/Sunday, 0 otherwise)

### Device
- **Device Type**: Mobile, Desktop, Tablet (one-hot encoded)
- **OS**: iOS, Android, Windows, Mac, Other (one-hot encoded, optional)

### Custom Features
Add your own features:

```yaml
custom:
  user_segment: ["high_value", "medium_value", "low_value"]
  purchase_history: ["new", "returning", "vip"]
  campaign_type: ["awareness", "conversion", "retargeting"]
```

## How It Works

### Learning Algorithm

The contextual bandit uses **LinUCB** (Linear Upper Confidence Bound):

1. **Linear Model**: For each arm, learn: `reward = context^T * theta_arm`
2. **Ridge Regression**: Update `theta_arm` using ridge regression with incremental updates
3. **UCB Selection**: Select arm with highest: `context^T * theta_arm + alpha * confidence`
4. **Exploration**: The `alpha` parameter controls exploration vs exploitation

### Context Flow

```
User Request → Context Extraction → Feature Encoding → Arm Selection → Update Model
```

1. **Context Extraction**: Extract features from user data and timestamp
2. **Feature Encoding**: Convert to one-hot encoded vector
3. **Arm Selection**: Use LinUCB to select best arm for this context
4. **Update Model**: Update linear model with observed reward

### Fallback Behavior

- If `contextual.enabled = false`: Uses standard `ThompsonSamplingAgent`
- If context is `None`: Falls back to standard arm selection
- If context is provided: Uses contextual LinUCB selection

## Performance Tracking

The contextual agent tracks performance by context:

```python
# Get contextual performance breakdown
contextual_perf = agent.get_contextual_performance()

# Example output:
# {
#   'age_25-34_gender_male_hour_14': {
#     'Arm(platform=Google, ...)': {'avg_reward': 1.5, 'trials': 100},
#     'Arm(platform=Meta, ...)': {'avg_reward': 1.2, 'trials': 80}
#   },
#   ...
# }
```

## Configuration Options

### `contextual.enabled`
- **Type**: `boolean`
- **Default**: `false`
- **Description**: Enable/disable contextual bandit mode

### `contextual.alpha`
- **Type**: `float`
- **Default**: `1.0`
- **Description**: Exploration parameter for LinUCB (higher = more exploration)

### `contextual.features`
- **Type**: `dict`
- **Description**: Feature configuration (see Supported Features above)

## Comparison: Standard vs Contextual

| Feature | Standard Bandit | Contextual Bandit |
|---------|----------------|-------------------|
| **Learning** | Arm-level performance | Context-arm interactions |
| **Selection** | Thompson Sampling | LinUCB with context |
| **Features** | Arm attributes only | Arm + user context |
| **Granularity** | "Google Search is best" | "Google Search is best for 25-34 age group in evening" |
| **Complexity** | Lower | Higher (more parameters) |
| **Data Needs** | Arm performance only | Arm performance + context |
| **Use Case** | Simple optimization | Granular, personalized optimization |

## Best Practices

1. **Start Simple**: Begin with standard bandit, then enable contextual if needed
2. **Feature Selection**: Only enable features that are likely to affect performance
3. **Data Requirements**: Contextual bandits need more data to learn (more parameters)
4. **Alpha Tuning**: Adjust `alpha` based on exploration needs (higher for new campaigns)
5. **Custom Features**: Add domain-specific features that matter for your use case

## Limitations

1. **Linear Model**: Assumes linear relationships (can be extended to non-linear)
2. **Feature Dimension**: Large feature dimensions require more data
3. **Cold Start**: New context-arm combinations need exploration time
4. **Computational Cost**: Slightly higher than standard bandit (matrix operations)

## Future Enhancements

- Non-linear models (neural networks, kernel methods)
- Feature selection/importance
- Context clustering
- Multi-objective contextual optimization
- Real-time context streaming

## References

- **LinUCB**: Li et al. (2010) "A Contextual-Bandit Approach to Personalized News Article Recommendation"
- **Contextual Bandits**: General framework for learning with context
