#def main():
 #   print("Ads Bandit Optimizer is set up correctly.")

#if __name__ == "__main__":
    #main()


"""
Creates all possible combinations of platform, channel, creative, bid → stored as “arms”

Creates an AdEnvironment with configurable CTR, CVR, revenue, and CPC

Randomly picks 5 arms and simulates one round each

Prints the reward metrics: clicks, conversions, revenue, cost, and ROAS
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.arms import ArmManager
from src.bandit_ads.env import AdEnvironment
import random

def main():
    # Step 1: Define some sample options
    platforms = ["Google", "Meta", "The Trade Desk"]
    channels = ["Search", "Display", "Social"]
    creatives = ["Creative A", "Creative B"]
    bids = [1.0, 2.0]  # example bid values

    # Step 2: Generate all possible arms
    arm_manager = ArmManager(platforms, channels, creatives, bids)
    all_arms = arm_manager.get_arms()
    print(f"Total arms created: {len(all_arms)}")
    print("Sample arms:", all_arms[:5])  # show first 5 for quick check

    # Step 3: Create the ad environment
    env = AdEnvironment(
        arm_params={
            "ctr": 0.05,      # 5% click-through rate
            "cvr": 0.1,       # 10% conversion rate
            "revenue": 10.0,  # $10 per conversion
            "cpc": 1.0        # $1 cost per click
        }
    )

    # Step 4: Simulate pulling 5 random arms
    print("\nSimulating ad pulls...")
    for i in range(5):
        arm = random.choice(all_arms)
        result = env.step(arm)
        print(f"Pull {i+1}: {arm} -> Reward metrics: {result}")

if __name__ == "__main__":
    main()

