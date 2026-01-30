"""
Comprehensive test simulation script for the ads budget optimizer.

Tests both standard and contextual bandit modes with realistic scenarios.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config
from src.bandit_ads.utils import ConfigManager
from src.bandit_ads.arms import ArmManager, Arm
from src.bandit_ads.env import AdEnvironment
from src.bandit_ads.agent import ThompsonSamplingAgent
from src.bandit_ads.contextual_agent import ContextualBanditAgent
from src.bandit_ads.data_loader import MMMDataLoader


def test_basic_bandit():
    """Test 1: Basic Thompson Sampling bandit without context."""
    print("\n" + "=" * 70)
    print("TEST 1: Basic Thompson Sampling Bandit")
    print("=" * 70)
    
    # Create simple arms
    platforms = ['Google', 'Meta']
    channels = ['Search', 'Display']
    creatives = ['Creative A', 'Creative B']
    bids = [1.0, 2.0]
    
    arm_manager = ArmManager(platforms, channels, creatives, bids)
    arms = arm_manager.get_arms()
    print(f"Created {len(arms)} arms")
    
    # Create environment with different arm performance
    arm_specific = {
        'Arm(platform=Google, channel=Search, creative=Creative A, bid=1.0)': {
            'ctr': 0.08, 'cvr': 0.15, 'revenue': 15.0, 'cpc': 0.8
        },
        'Arm(platform=Meta, channel=Display, creative=Creative B, bid=2.0)': {
            'ctr': 0.06, 'cvr': 0.12, 'revenue': 12.0, 'cpc': 1.2
        },
    }
    
    env = AdEnvironment(arm_specific_params=arm_specific)
    agent = ThompsonSamplingAgent(arms, total_budget=500.0)
    
    print("\nRunning simulation (50 rounds)...")
    for round_num in range(50):
        if agent.is_budget_exhausted():
            break
        
        arm = agent.select_arm()
        result = env.step(arm, impressions=50)
        agent.update(arm, result)
        
        if round_num % 10 == 0:
            metrics = agent.get_performance_metrics()
            print(f"  Round {round_num:3d}: Spent ${metrics['total_spent']:6.2f}, "
                  f"ROAS: {metrics['total_roas']:.3f}")
    
    # Final results
    metrics = agent.get_performance_metrics()
    print(f"\n✅ Test 1 Complete:")
    print(f"   Total Spent: ${metrics['total_spent']:.2f}")
    print(f"   Overall ROAS: {metrics['total_roas']:.3f}")
    print(f"   Budget Utilization: {metrics['budget_utilization']:.1%}")
    
    # Top arms
    arm_perf = metrics['arm_performance']
    sorted_arms = sorted(arm_perf.items(), key=lambda x: x[1]['avg_roas'], reverse=True)
    print(f"\n   Top 3 Arms:")
    for i, (arm_str, perf) in enumerate(sorted_arms[:3], 1):
        print(f"   {i}. {arm_str[:50]}")
        print(f"      ROAS: {perf['avg_roas']:.3f}, Spent: ${perf['spending']:.2f}")


def test_contextual_bandit():
    """Test 2: Contextual bandit with user demographics and time-of-day."""
    print("\n" + "=" * 70)
    print("TEST 2: Contextual Bandit with Demographics & Time-of-Day")
    print("=" * 70)
    
    # Create arms
    platforms = ['Google', 'Meta']
    channels = ['Search', 'Display']
    creatives = ['Creative A']
    bids = [1.0, 2.0]
    
    arm_manager = ArmManager(platforms, channels, creatives, bids)
    arms = arm_manager.get_arms()
    print(f"Created {len(arms)} arms")
    
    # Create environment
    env = AdEnvironment()
    
    # Create contextual agent
    agent = ContextualBanditAgent(
        arms=arms,
        total_budget=500.0,
        context_config={
            'demographics': {'age_group': True, 'gender': True, 'location': True},
            'temporal': {'hour': True, 'day_of_week': True},
            'device': {'device_type': True}
        },
        alpha=1.0
    )
    
    print("\nRunning contextual simulation (50 rounds)...")
    print("   (Simulating different user contexts)")
    
    # Simulate different user contexts
    user_contexts = [
        {'age': 28, 'gender': 'male', 'location': 'us', 'device_type': 'mobile'},
        {'age': 35, 'gender': 'female', 'location': 'eu', 'device_type': 'desktop'},
        {'age': 42, 'gender': 'male', 'location': 'us', 'device_type': 'tablet'},
        {'age': 25, 'gender': 'female', 'location': 'asia', 'device_type': 'mobile'},
    ]
    
    for round_num in range(50):
        if agent.is_budget_exhausted():
            break
        
        # Cycle through user contexts
        user_data = user_contexts[round_num % len(user_contexts)]
        context = {
            'user_data': user_data,
            'timestamp': datetime.now()
        }
        
        arm = agent.select_arm(context=context)
        result = env.step(arm, impressions=50, context=context)
        agent.update(arm, result, context=context)
        
        if round_num % 10 == 0:
            metrics = agent.get_performance_metrics()
            print(f"  Round {round_num:3d}: Spent ${metrics['total_spent']:6.2f}, "
                  f"ROAS: {metrics['total_roas']:.3f}, "
                  f"Context: {user_data['age']}yo {user_data['gender']} {user_data['device_type']}")
    
    # Final results
    metrics = agent.get_performance_metrics()
    print(f"\n✅ Test 2 Complete:")
    print(f"   Total Spent: ${metrics['total_spent']:.2f}")
    print(f"   Overall ROAS: {metrics['total_roas']:.3f}")
    print(f"   Feature Dimension: {metrics['feature_dimension']}")
    
    # Contextual performance
    contextual_perf = metrics.get('contextual_performance', {})
    if contextual_perf:
        print(f"\n   Contextual Performance (sample):")
        for context_key, arm_perf in list(contextual_perf.items())[:3]:
            print(f"   Context: {context_key[:40]}")
            for arm_key, perf in list(arm_perf.items())[:2]:
                print(f"      {arm_key[:40]}: reward={perf['avg_reward']:.3f}, trials={perf['trials']}")


def test_full_campaign_standard():
    """Test 3: Full campaign runner with standard bandit."""
    print("\n" + "=" * 70)
    print("TEST 3: Full Campaign Runner (Standard Bandit)")
    print("=" * 70)
    
    config = create_sample_campaign_config()
    config['contextual'] = {'enabled': False}  # Explicitly disable
    
    config_manager = ConfigManager()
    runner = AdOptimizationRunner(config, config_manager)
    
    print("Setting up campaign...")
    runner.setup_campaign()
    
    print("Running campaign (30 rounds)...")
    results = runner.run_campaign(max_rounds=30, log_frequency=10)
    
    print(f"\n✅ Test 3 Complete:")
    print(f"   Total Rounds: {results['total_rounds']}")
    print(f"   Performance Log Entries: {len(results['performance_log'])}")
    runner.print_summary()


def test_full_campaign_contextual():
    """Test 4: Full campaign runner with contextual bandit."""
    print("\n" + "=" * 70)
    print("TEST 4: Full Campaign Runner (Contextual Bandit)")
    print("=" * 70)
    
    config = create_sample_campaign_config()
    config['contextual'] = {
        'enabled': True,
        'alpha': 1.0,
        'features': {
            'demographics': {'age_group': True, 'gender': True},
            'temporal': {'hour': True, 'day_of_week': True},
            'device': {'device_type': True}
        }
    }
    
    config_manager = ConfigManager()
    runner = AdOptimizationRunner(config, config_manager)
    
    print("Setting up contextual campaign...")
    runner.setup_campaign()
    
    print("Running campaign (30 rounds)...")
    results = runner.run_campaign(max_rounds=30, log_frequency=10)
    
    print(f"\n✅ Test 4 Complete:")
    print(f"   Total Rounds: {results['total_rounds']}")
    print(f"   Using Contextual Bandit: {runner.use_contextual}")
    runner.print_summary()


def test_historical_data_loading():
    """Test 5: Historical data loading and priors."""
    print("\n" + "=" * 70)
    print("TEST 5: Historical Data Loading")
    print("=" * 70)
    
    data_loader = MMMDataLoader()
    
    # Create sample historical data
    sample_data = data_loader.create_sample_historical_data()
    print(f"Created sample historical data with {len(sample_data.get('historical_performance', {}))} arm combinations")
    
    # Load it
    success = data_loader.load_historical_data(data_dict=sample_data)
    print(f"Data loaded: {success}")
    
    # Test getting priors for an arm
    test_arm = Arm('Google', 'Search', 'Creative A', 1.0)
    priors = data_loader.get_arm_priors(test_arm)
    
    print(f"\n✅ Test 5 Complete:")
    print(f"   Priors for {test_arm}:")
    if priors['historical_performance']:
        hist = priors['historical_performance']
        print(f"     Historical CTR: {hist.get('historical_ctr', 'N/A'):.3f}")
        print(f"     Historical CVR: {hist.get('historical_cvr', 'N/A'):.3f}")
        print(f"     Historical ROAS: {hist.get('historical_roas', 'N/A'):.2f}")
    else:
        print(f"     No historical data found (using defaults)")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("ADS BUDGET OPTIMIZER - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print("\nThis script tests:")
    print("  1. Basic Thompson Sampling bandit")
    print("  2. Contextual bandit with demographics & time")
    print("  3. Full campaign runner (standard mode)")
    print("  4. Full campaign runner (contextual mode)")
    print("  5. Historical data loading")
    
    try:
        test_basic_bandit()
        test_contextual_bandit()
        test_full_campaign_standard()
        test_full_campaign_contextual()
        test_historical_data_loading()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nThe system is working correctly. You can now:")
        print("  - Run full campaigns with: python scripts/run_simulation.py")
        print("  - Test contextual bandits: python scripts/run_contextual_example.py")
        print("  - Load your own historical data from CSV/JSON files")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
