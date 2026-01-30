"""
Example script demonstrating contextual bandit usage.

Shows how to use the contextual bandit agent with user demographics,
time-of-day, and other contextual features.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config
from src.bandit_ads.utils import ConfigManager
from datetime import datetime


def create_contextual_campaign_config():
    """Create a campaign config with contextual bandit enabled."""
    config = create_sample_campaign_config()
    
    # Enable contextual bandit
    config['contextual'] = {
        'enabled': True,
        'alpha': 1.0,  # Exploration parameter
        'features': {
            'demographics': {
                'age_group': True,
                'gender': True,
                'location': True
            },
            'temporal': {
                'hour': True,
                'day_of_week': True,
                'month': True,
                'is_weekend': True
            },
            'device': {
                'device_type': True,
                'os': False
            },
            'custom': {
                # Example custom features
                # 'user_segment': ['high_value', 'medium_value', 'low_value']
            }
        }
    }
    
    return config


def main():
    """Run a contextual bandit campaign example."""
    print("=" * 60)
    print("Contextual Bandit Example")
    print("=" * 60)
    print("\nThis example demonstrates:")
    print("  - Contextual bandit with user demographics")
    print("  - Time-of-day and temporal features")
    print("  - Device type features")
    print("  - Learning arm performance conditioned on context")
    print()
    
    # Create config
    config = create_contextual_campaign_config()
    
    # Create runner
    config_manager = ConfigManager()
    runner = AdOptimizationRunner(config, config_manager)
    
    # Setup campaign
    print("Setting up contextual bandit campaign...")
    runner.setup_campaign()
    
    # Run campaign
    print("\nRunning campaign with contextual features...")
    results = runner.run_campaign(max_rounds=100, log_frequency=25)
    
    # Print summary
    runner.print_summary()
    
    # Show contextual performance if available
    if hasattr(runner.agent, 'get_contextual_performance'):
        print("\n" + "=" * 60)
        print("Contextual Performance Breakdown")
        print("=" * 60)
        contextual_perf = runner.agent.get_contextual_performance()
        
        if contextual_perf:
            print(f"\nFound {len(contextual_perf)} distinct contexts")
            for context_key, arm_perf in list(contextual_perf.items())[:5]:  # Show first 5
                print(f"\nContext: {context_key}")
                for arm_key, perf in list(arm_perf.items())[:3]:  # Show top 3 arms
                    print(f"  {arm_key}: avg_reward={perf['avg_reward']:.3f}, trials={perf['trials']}")
        else:
            print("No contextual performance data yet (needs more rounds)")
    
    print("\n" + "=" * 60)
    print("Campaign Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
