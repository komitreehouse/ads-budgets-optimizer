# Ads Budgets Optimizer

A production-ready multi-armed bandit system for optimizing advertising spend across platforms, channels, creatives, and bidding strategies. Features comprehensive MMM (Marketing Mix Modeling) integration and real-time API connectivity.

## Features

- **Multi-Armed Bandit Optimization**: Thompson Sampling with risk constraints
- **MMM Integration**: Seasonality, competitive effects, carryover/ad stock, external factors
- **Real-Time API Support**: Google Ads, Meta Ads, The Trade Desk connectors
- **Historical Data Loading**: Initialize priors from past performance
- **Budget-Constrained Optimization**: Intelligent budget allocation across arms
- **ROAS-Focused**: Optimizes for Return on Ad Spend
- **Production-Ready**: Logging, error handling, configuration management

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd ads-budgets-optimizer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Basic Simulation

```bash
python scripts/run_simulation.py
```

### Full Campaign with Configuration

```python
from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config
from src.bandit_ads.utils import ConfigManager

# Load configuration
config_manager = ConfigManager('config.yaml')
config = create_sample_campaign_config()

# Run campaign
runner = AdOptimizationRunner(config, config_manager)
runner.setup_campaign()
results = runner.run_campaign(max_rounds=100)
runner.print_summary()
```

## Configuration

### Configuration File

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
# Logging
logging:
  level: INFO
  file: logs/bandit_ads.log

# Agent settings
agent:
  total_budget: 5000.0
  risk_tolerance: 0.3
  variance_limit: 0.1
```

### Environment Variables

Set API credentials via environment variables:

```bash
export GOOGLE_ADS_CLIENT_ID="your_client_id"
export GOOGLE_ADS_CLIENT_SECRET="your_client_secret"
export GOOGLE_ADS_REFRESH_TOKEN="your_refresh_token"
export META_ACCESS_TOKEN="your_meta_token"
```

Or use a `.env` file:

```
GOOGLE_ADS_CLIENT_ID=your_client_id
GOOGLE_ADS_CLIENT_SECRET=your_client_secret
```

## Real-Time API Integration

### Setting Up API Connectors

```python
from src.bandit_ads.api_connectors import create_api_connector
from src.bandit_ads.realtime_env import RealTimeEnvironment

# Create connectors
google_connector = create_api_connector('google', {
    'client_id': 'your_client_id',
    'client_secret': 'your_client_secret',
    'refresh_token': 'your_refresh_token',
    'developer_token': 'your_developer_token',
    'customer_id': 'your_customer_id'
})

meta_connector = create_api_connector('meta', {
    'access_token': 'your_access_token',
    'app_id': 'your_app_id',
    'app_secret': 'your_app_secret',
    'ad_account_id': 'your_ad_account_id'
})

# Create real-time environment
env = RealTimeEnvironment(
    api_connectors={
        'google': google_connector,
        'meta': meta_connector
    },
    fallback_to_simulated=True  # Use simulation if APIs fail
)
```

## Project Structure

```
ads-budgets-optimizer/
├── src/
│   └── bandit_ads/
│       ├── __init__.py
│       ├── agent.py          # Thompson Sampling bandit agent
│       ├── arms.py           # Arm definitions and management
│       ├── env.py            # Simulated environment
│       ├── realtime_env.py   # Real-time API environment
│       ├── api_connectors.py # API connectors (Google, Meta, TTD)
│       ├── data_loader.py    # Historical data loading
│       ├── runner.py         # Campaign orchestration
│       ├── utils.py          # Utilities (logging, config, errors)
│       └── metrics.py        # Performance metrics
├── scripts/
│   └── run_simulation.py     # Basic simulation script
├── tests/                    # Test files
├── config.example.yaml       # Example configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_agent.py

# With coverage
pytest --cov=src/bandit_ads tests/
```

## Logging

Logs are written to console and optionally to a file:

```python
from src.bandit_ads.utils import setup_logging

setup_logging(log_level='DEBUG', log_file='logs/app.log')
```

## Error Handling

The system includes comprehensive error handling:

- **Retry Logic**: Automatic retries for API calls
- **Fallback**: Graceful fallback to simulation if APIs fail
- **Validation**: Input validation for all parameters
- **Logging**: Detailed error logging for debugging

## Advanced Features

### MMM Factors

Configure seasonality, competition, and carryover effects:

```yaml
mmm_factors:
  seasonality:
    Q4:
      Search: 1.20
      Display: 1.25
      Social: 1.30
  carryover:
    decay_rate: 0.8
    max_stock: 2.0
```

### Risk Constraints

Control risk tolerance:

```python
agent = ThompsonSamplingAgent(
    arms=arms,
    total_budget=10000.0,
    risk_tolerance=0.2,    # Lower = more risk-averse
    variance_limit=0.05   # Max variance allowed
)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub.