"""
Example script showing how to load and use mock historical data.

This demonstrates loading historical data from JSON or CSV files
and using it to initialize the bandit agent with priors.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config
from src.bandit_ads.utils import ConfigManager
from src.bandit_ads.data_loader import MMMDataLoader


def example_with_json_data():
    """Example using JSON historical data."""
    print("\n" + "=" * 70)
    print("Example: Loading Historical Data from JSON")
    print("=" * 70)
    
    # Create campaign config
    config = create_sample_campaign_config()
    
    # Enable historical data loading
    config['historical_data'] = {
        'enabled': True,
        'file_path': 'data/mock_historical_data.json'  # Relative to project root
    }
    
    # Create runner
    config_manager = ConfigManager()
    runner = AdOptimizationRunner(config, config_manager)
    
    print("Setting up campaign with historical data...")
    runner.setup_campaign()
    
    print("\nRunning campaign (50 rounds)...")
    results = runner.run_campaign(max_rounds=50, log_frequency=25)
    
    print("\n" + "=" * 70)
    print("Results Summary")
    print("=" * 70)
    runner.print_summary()
    
    print("\n✅ Campaign completed with historical data priors!")


def example_with_csv_data():
    """Example using CSV historical data."""
    print("\n" + "=" * 70)
    print("Example: Loading Historical Data from CSV")
    print("=" * 70)
    
    # Create campaign config
    config = create_sample_campaign_config()
    
    # Enable historical data loading from CSV
    config['historical_data'] = {
        'enabled': True,
        'file_path': 'data/mock_historical_data.csv'
    }
    
    # Create runner
    config_manager = ConfigManager()
    runner = AdOptimizationRunner(config, config_manager)
    
    print("Setting up campaign with CSV historical data...")
    runner.setup_campaign()
    
    print("\nRunning campaign (50 rounds)...")
    results = runner.run_campaign(max_rounds=50, log_frequency=25)
    
    print("\n" + "=" * 70)
    print("Results Summary")
    print("=" * 70)
    runner.print_summary()
    
    print("\n✅ Campaign completed with CSV historical data!")


def example_programmatic_data():
    """Example creating historical data programmatically."""
    print("\n" + "=" * 70)
    print("Example: Creating Historical Data Programmatically")
    print("=" * 70)
    
    # Create data loader
    data_loader = MMMDataLoader()
    
    # Create custom historical data
    custom_data = {
        'historical_performance': {
            'Google_Search_Creative A_1.0': {
                'historical_ctr': 0.09,
                'historical_cvr': 0.16,
                'historical_roas': 1.75,
                'spend_baseline': 5000.0,
                'variance_ctr': 0.001,
                'variance_cvr': 0.003
            },
            'Meta_Display_Creative A_1.0': {
                'historical_ctr': 0.03,
                'historical_cvr': 0.08,
                'historical_roas': 1.20,
                'spend_baseline': 3000.0,
                'variance_ctr': 0.0008,
                'variance_cvr': 0.002
            }
        }
    }
    
    # Load it
    data_loader.load_historical_data(data_dict=custom_data)
    
    print("Created and loaded custom historical data:")
    print(f"  - {len(custom_data['historical_performance'])} arm combinations")
    
    # Now use it in a campaign
    config = create_sample_campaign_config()
    config['historical_data'] = {'enabled': True}
    
    # Manually set the data loader
    runner = AdOptimizationRunner(config)
    runner.data_loader = data_loader  # Use our custom data
    
    print("\nSetting up campaign with programmatic data...")
    runner.setup_campaign()
    
    print("\nRunning campaign (30 rounds)...")
    results = runner.run_campaign(max_rounds=30, log_frequency=15)
    
    print("\n✅ Campaign completed with programmatic historical data!")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("MOCK DATA LOADING EXAMPLES")
    print("=" * 70)
    print("\nThis script demonstrates:")
    print("  1. Loading historical data from JSON file")
    print("  2. Loading historical data from CSV file")
    print("  3. Creating historical data programmatically")
    
    try:
        # Check if data files exist
        json_path = project_root / 'data' / 'mock_historical_data.json'
        csv_path = project_root / 'data' / 'mock_historical_data.csv'
        
        if not json_path.exists():
            print(f"\n⚠️  Warning: {json_path} not found. Skipping JSON example.")
        else:
            example_with_json_data()
        
        if not csv_path.exists():
            print(f"\n⚠️  Warning: {csv_path} not found. Skipping CSV example.")
        else:
            example_with_csv_data()
        
        example_programmatic_data()
        
        print("\n" + "=" * 70)
        print("✅ ALL EXAMPLES COMPLETED!")
        print("=" * 70)
        print("\nYou can now:")
        print("  - Use data/mock_historical_data.json in your campaigns")
        print("  - Use data/mock_historical_data.csv in your campaigns")
        print("  - Create your own historical data files")
        print("  - Generate data programmatically")
        
    except Exception as e:
        print(f"\n❌ Example failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
