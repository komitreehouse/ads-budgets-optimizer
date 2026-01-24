import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.arms import ArmManager, Arm
from src.bandit_ads.env import AdEnvironment

def test_enhanced_environment():
    """Test the enhanced environment with arm-specific parameters"""
    print("Testing Enhanced AdEnvironment...")

    # Create arm manager
    platforms = ['Google', 'Meta']
    channels = ['Search', 'Display']
    creatives = ['Creative A']
    bids = [1.0, 2.0]

    arm_manager = ArmManager(platforms, channels, creatives, bids)
    arms = arm_manager.get_arms()
    print(f"Created {len(arms)} arms")

    # Create environment with arm-specific parameters
    arm_specific = {
        'Arm(platform=Google, channel=Search, creative=Creative A, bid=1.0)': {
            'ctr': 0.08,  # 8% CTR for Google Search
            'cvr': 0.15   # 15% CVR
        },
        'Arm(platform=Meta, channel=Display, creative=Creative A, bid=1.0)': {
            'ctr': 0.03,  # 3% CTR for Meta Display
            'cvr': 0.08   # 8% CVR
        }
    }

    env = AdEnvironment(arm_specific_params=arm_specific)

    # Test a few arms with multiple impressions
    print("\nTesting arms with 1000 impressions each:")
    for arm in arms[:4]:
        result = env.step(arm, impressions=1000)
        actual_ctr = result["clicks"] / result["impressions"]
        actual_cvr = result["conversions"] / result["clicks"] if result["clicks"] > 0 else 0

        expected_ctr = arm_specific.get(str(arm), {}).get('ctr', env.global_params['ctr'])
        expected_cvr = arm_specific.get(str(arm), {}).get('cvr', env.global_params['cvr'])

        print(f"{arm}:")
        print(f"  Expected CTR: {expected_ctr:.3f}, Actual CTR: {result['clicks']/result['impressions']:.3f}")
        print(f"  Expected CVR: {expected_cvr:.3f}, Actual CVR: {result['conversions']/result['clicks']:.3f}" if result['clicks'] > 0 else f"  Expected CVR: {expected_cvr:.3f}, Actual CVR: 0.000")
        print(f"  ROAS: {result['roas']:.2f}")
        print()

if __name__ == "__main__":
    test_enhanced_environment()