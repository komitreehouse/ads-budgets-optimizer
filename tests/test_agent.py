import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.arms import ArmManager
from src.bandit_ads.env import AdEnvironment
from src.bandit_ads.agent import ThompsonSamplingAgent

def test_bandit_agent():
    """Test the Thompson Sampling bandit agent"""
    print("Testing Thompson Sampling Agent...")

    # Create arms
    platforms = ['Google', 'Meta']
    channels = ['Search', 'Display']
    creatives = ['Creative A', 'Creative B']
    bids = [1.0, 2.0]

    arm_manager = ArmManager(platforms, channels, creatives, bids)
    arms = arm_manager.get_arms()
    print(f"Created {len(arms)} arms")

    # Create environment with different performance for different arms
    arm_specific = {
        # High-performing arms
        'Arm(platform=Google, channel=Search, creative=Creative A, bid=1.0)': {
            'ctr': 0.08, 'cvr': 0.15, 'revenue': 15.0, 'cpc': 0.8
        },
        'Arm(platform=Meta, channel=Display, creative=Creative B, bid=2.0)': {
            'ctr': 0.06, 'cvr': 0.12, 'revenue': 12.0, 'cpc': 1.2
        },
        # Low-performing arms
        'Arm(platform=Google, channel=Display, creative=Creative A, bid=1.0)': {
            'ctr': 0.02, 'cvr': 0.05, 'revenue': 8.0, 'cpc': 1.5
        }
    }

    env = AdEnvironment(arm_specific_params=arm_specific)

    # Create agent with $1000 budget
    agent = ThompsonSamplingAgent(arms, total_budget=1000.0)

    # Run simulation for 100 rounds
    print("\nRunning simulation...")
    for round_num in range(100):
        if agent.is_budget_exhausted():
            print(f"Budget exhausted at round {round_num}")
            break

        # Select arm and simulate
        arm = agent.select_arm()
        result = env.step(arm, impressions=100)  # 100 impressions per round

        # Update agent
        agent.update(arm, result)

        if round_num % 20 == 0:
            metrics = agent.get_performance_metrics()
            print(f"  Round {round_num}: Spent ${metrics['total_spent']:.2f}")

    # Final performance
    metrics = agent.get_performance_metrics()
    print("\nFinal Results:")
    print(f"Total Spent: ${metrics['total_spent']:.2f}")
    print(f"Overall ROAS: {metrics['total_roas']:.2f}")
    print("\nTop performing arms:")
    arm_perf = metrics['arm_performance']
    sorted_arms = sorted(arm_perf.items(), key=lambda x: x[1]['avg_roas'], reverse=True)

    for arm_str, perf in sorted_arms[:3]:
        print(f"  {arm_str}: ROAS={perf['avg_roas']:.2f}, spent=${perf['spending']:.2f}")

if __name__ == "__main__":
    test_bandit_agent()