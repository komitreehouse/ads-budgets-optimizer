import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config

def test_runner():
    """Test the AdOptimizationRunner"""
    print("Testing AdOptimizationRunner...")

    # Create and run a sample campaign
    config = create_sample_campaign_config()
    runner = AdOptimizationRunner(config)
    runner.setup_campaign()
    results = runner.run_campaign(max_rounds=50, log_frequency=25)  # Short test
    runner.print_summary()

    print(f"\nCampaign completed in {len(results['performance_log'])} logged intervals")
    print(f"Total rounds: {results['total_rounds']}")

if __name__ == "__main__":
    test_runner()