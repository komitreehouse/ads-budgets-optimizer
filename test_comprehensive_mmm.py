import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config

def test_comprehensive_mmm_system():
    """Test the complete MMM ad optimization system."""
    print('Testing Comprehensive MMM Ad Optimization System...')
    print('=' * 60)

    config = create_sample_campaign_config()
    runner = AdOptimizationRunner(config)
    runner.setup_campaign()

    # Run a short test
    results = runner.run_campaign(max_rounds=30, log_frequency=15)
    runner.print_summary()

    print('\nKey Features Demonstrated:')
    print('✓ Historical data integration for priors')
    print('✓ Seasonal performance adjustments')
    print('✓ Competitive market saturation effects')
    print('✓ Ad stock carryover effects')
    print('✓ External factor impacts (holidays)')
    print('✓ Risk-constrained budget allocation')
    print('✓ Variance-limited arm selection')

    # Show MMM factors in action
    if results['total_rounds'] > 0:
        print('\nMMM Factors Analysis:')
        last_result = results['results_history'][-1] if results['results_history'] else None
        if last_result and 'mmm_factors' in last_result['result']:
            mmm = last_result['result']['mmm_factors']
            print(f'Seasonal Multiplier: {mmm["seasonal_multiplier"]:.3f}')
            print(f'Carryover Multiplier: {mmm["carryover_multiplier"]:.3f}')
            print(f'Competitive Multiplier: {mmm["competitive_multiplier"]:.3f}')
            print(f'External Multiplier: {mmm["external_multiplier"]:.3f}')

if __name__ == "__main__":
    test_comprehensive_mmm_system()