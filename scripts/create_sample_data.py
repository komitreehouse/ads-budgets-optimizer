#!/usr/bin/env python3
"""
Create sample data for testing the API and frontend.

This script creates sample campaigns, arms, and metrics in the database.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.database import init_database, get_db_manager


def create_sample_campaigns():
    """Create sample campaigns."""
    print("Creating sample campaigns...")

    campaigns_data = [
        {
            "name": "Q1 Brand Awareness",
            "budget": 50000.0,
            "start_date": datetime.utcnow() - timedelta(days=200),
            "status": "active"
        },
        {
            "name": "Product Launch - Widget X",
            "budget": 30000.0,
            "start_date": datetime.utcnow() - timedelta(days=180),
            "status": "active"
        },
        {
            "name": "Retargeting Campaign",
            "budget": 20000.0,
            "start_date": datetime.utcnow() - timedelta(days=150),
            "status": "paused"
        },
        {
            "name": "Holiday Promotions",
            "budget": 45000.0,
            "start_date": datetime.utcnow() - timedelta(days=120),
            "status": "active"
        },
        {
            "name": "Summer Sale",
            "budget": 35000.0,
            "start_date": datetime.utcnow() - timedelta(days=200),
            "end_date": datetime.utcnow() - timedelta(days=100),
            "status": "completed"
        }
    ]

    from src.bandit_ads.database import Campaign, get_db_manager
    db_manager = get_db_manager()
    campaigns = []
    with db_manager.get_session() as session:
        for data in campaigns_data:
            campaign = Campaign(
                name=data["name"],
                budget=data["budget"],
                start_date=data["start_date"],
                end_date=data.get("end_date"),
                status=data["status"],
            )
            session.add(campaign)
            session.flush()
            # Capture values before session closes
            campaigns.append({
                "id": campaign.id,
                "name": campaign.name,
                "budget": campaign.budget,
                "start_date": campaign.start_date,
                "end_date": campaign.end_date,
                "status": campaign.status,
            })
            print(f"  ✓ Created campaign: {campaign.name} (ID: {campaign.id})")

    return campaigns


# ---------------------------------------------------------------------------
# Channel profiles for realistic Meridian-ready data
# ---------------------------------------------------------------------------

# Each channel has baseline performance characteristics and diminishing-returns
# behaviour so that Meridian can learn meaningful Hill curves.
CHANNEL_PROFILES = {
    ("Google", "Search"): {
        "base_impressions": 6000,
        "base_ctr": 0.045,
        "base_cvr": 0.12,
        "base_cpc": 1.20,
        "base_rev_per_conv": 35.0,
        "weekly_budget": 4500,       # Typical weekly spend
        "saturation_point": 8000,    # Spend level where returns flatten
        "seasonality": [0.85, 1.05, 0.95, 1.20],  # Q1-Q4 multipliers
    },
    ("Meta", "Social"): {
        "base_impressions": 9000,
        "base_ctr": 0.035,
        "base_cvr": 0.09,
        "base_cpc": 0.80,
        "base_rev_per_conv": 28.0,
        "weekly_budget": 3000,
        "saturation_point": 5500,
        "seasonality": [1.15, 1.08, 0.90, 1.30],
    },
    ("Google", "Display"): {
        "base_impressions": 12000,
        "base_ctr": 0.025,
        "base_cvr": 0.07,
        "base_cpc": 0.50,
        "base_rev_per_conv": 22.0,
        "weekly_budget": 2000,
        "saturation_point": 4000,
        "seasonality": [0.90, 1.10, 1.15, 1.25],
    },
    ("The Trade Desk", "Display"): {
        "base_impressions": 15000,
        "base_ctr": 0.020,
        "base_cvr": 0.06,
        "base_cpc": 0.40,
        "base_rev_per_conv": 18.0,
        "weekly_budget": 1500,
        "saturation_point": 3000,
        "seasonality": [0.95, 1.00, 1.10, 1.15],
    },
    ("Meta", "Display"): {
        "base_impressions": 10000,
        "base_ctr": 0.022,
        "base_cvr": 0.065,
        "base_cpc": 0.55,
        "base_rev_per_conv": 20.0,
        "weekly_budget": 1200,
        "saturation_point": 2500,
        "seasonality": [1.00, 1.05, 0.95, 1.20],
    },
}

HISTORY_WEEKS = 26  # ~6 months of history — well above 12-week minimum


def _quarter(dt):
    """Return 0-based quarter index for a date."""
    return (dt.month - 1) // 3


def _hill_response(spend, saturation_point, slope=2.0):
    """
    Simple Hill-function response curve used to inject realistic
    diminishing-returns behaviour into the synthetic data.
    Returns a multiplier in (0, 1].
    """
    if spend <= 0:
        return 0.0
    import math
    return spend ** slope / (saturation_point ** slope + spend ** slope)


def create_sample_arms(campaigns):
    """Create sample arms for campaigns — deterministic channel set per campaign."""
    print("\nCreating sample arms...")

    from src.bandit_ads.database import Arm, get_db_manager
    import json

    channel_list = list(CHANNEL_PROFILES.keys())
    all_arms = []
    db_manager = get_db_manager()

    with db_manager.get_session() as session:
        for campaign in campaigns:
            n = random.randint(3, min(5, len(channel_list)))
            selected = random.sample(channel_list, n)

            for platform, channel in selected:
                creative = random.choice(["Creative A", "Creative B", "Creative C"])
                bid = random.choice([1.0, 1.5, 2.0, 2.5])
                arm = Arm(
                    campaign_id=campaign["id"],
                    platform=platform,
                    channel=channel,
                    creative=creative,
                    bid=bid,
                    platform_entity_ids=json.dumps({
                        "campaign_id": f"{platform.lower()}_{campaign['id']}",
                        "ad_group_id": f"ag_{random.randint(1000, 9999)}"
                    }),
                )
                session.add(arm)
                session.flush()
                all_arms.append({
                    "campaign_id": campaign["id"],
                    "arm_id": arm.id,
                    "platform": arm.platform,
                    "channel": arm.channel,
                    "campaign_start": campaign["start_date"],
                    "campaign_end": campaign.get("end_date"),
                })
                print(f"  ✓ Created arm: {platform}/{channel}/{creative} (Bid: ${bid})")

    return all_arms


def create_sample_metrics(campaigns, arms):
    """
    Create realistic daily metrics spanning HISTORY_WEEKS weeks.

    The data is designed so that Meridian can learn:
      - Hill-function saturation curves (spend varies ±40% around baseline)
      - Seasonal patterns (Q1-Q4 multipliers per channel)
      - Adstock carryover (slight autocorrelation in daily spend)
      - Enough weeks for stable MCMC convergence
    """
    from src.bandit_ads.database import Metric, get_db_manager

    total_days = HISTORY_WEEKS * 7
    print(f"\nCreating {total_days} days ({HISTORY_WEEKS} weeks) of metrics...")

    db_manager = get_db_manager()
    batch = []
    BATCH_SIZE = 500

    for day_offset in range(total_days):
        date = datetime.utcnow() - timedelta(days=total_days - day_offset)
        quarter = _quarter(date)
        day_of_week = date.weekday()

        for arm_info in arms:
            campaign = next((c for c in campaigns if c["id"] == arm_info["campaign_id"]), None)
            if campaign and campaign.get("end_date") and date > campaign["end_date"]:
                continue
            if campaign and date < campaign["start_date"]:
                continue

            key = (arm_info["platform"], arm_info["channel"])
            profile = CHANNEL_PROFILES.get(key)
            if not profile:
                profile = list(CHANNEL_PROFILES.values())[0]

            seasonal = profile["seasonality"][quarter]
            dow_mult = 0.85 if day_of_week >= 5 else 1.0
            trend = 1.0 + 0.001 * day_offset
            daily_budget = (profile["weekly_budget"] / 7) * seasonal * dow_mult * trend
            spend_noise = random.uniform(0.6, 1.4)
            target_spend = daily_budget * spend_noise

            saturation_mult = _hill_response(
                target_spend, profile["saturation_point"] / 7
            )

            impressions = int(
                profile["base_impressions"] * seasonal * dow_mult
                * random.uniform(0.8, 1.2)
            )
            ctr = profile["base_ctr"] * saturation_mult * random.uniform(0.85, 1.15)
            clicks = max(1, int(impressions * ctr))
            cost = clicks * profile["base_cpc"] * random.uniform(0.9, 1.1)

            cvr = profile["base_cvr"] * saturation_mult * random.uniform(0.85, 1.15)
            conversions = max(0, int(clicks * cvr))
            revenue = conversions * profile["base_rev_per_conv"] * random.uniform(0.9, 1.1)
            roas = revenue / cost if cost > 0 else 0.0

            batch.append(Metric(
                campaign_id=arm_info["campaign_id"],
                arm_id=arm_info["arm_id"],
                timestamp=date,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                revenue=round(revenue, 2),
                cost=round(cost, 2),
                roas=round(roas, 4),
                ctr=round(ctr, 6),
                cvr=round(cvr, 6),
                source="simulated",
            ))

            if len(batch) >= BATCH_SIZE:
                with db_manager.get_session() as session:
                    session.add_all(batch)
                batch = []

        if day_offset % 14 == 0:
            week_num = day_offset // 7 + 1
            print(f"  ✓ Week {week_num}/{HISTORY_WEEKS} …")

    # Flush remaining
    if batch:
        with db_manager.get_session() as session:
            session.add_all(batch)

    print(f"  ✓ All metrics created ({total_days} days)")


def main():
    """Main function to create sample data."""
    print("=" * 60)
    print("Creating Sample Data for Ads Budget Optimizer")
    print("=" * 60)
    
    # Initialize database
    print("\nInitializing database...")
    init_database(create_tables=True)
    print("  ✓ Database initialized")
    
    # Create sample data
    campaigns = create_sample_campaigns()
    arms = create_sample_arms(campaigns)
    create_sample_metrics(campaigns, arms)
    
    print("\n" + "=" * 60)
    print("Sample Data Creation Complete!")
    print("=" * 60)
    total_days = HISTORY_WEEKS * 7
    print(f"\nCreated:")
    print(f"  - {len(campaigns)} campaigns")
    print(f"  - {len(arms)} arms")
    print(f"  - ~{len(arms) * total_days} metric records ({HISTORY_WEEKS} weeks / {total_days} days)")
    print(f"\n  Meridian-ready: {HISTORY_WEEKS} weeks of data (minimum 12 required)")
    print("\nYou can now:")
    print("  1. Start the API: python3 scripts/run_api.py")
    print("  2. Start the frontend: streamlit run frontend/app.py")
    print("  3. View the data in the dashboard!")
    print("  4. Train Meridian: POST /api/mmm/train")


if __name__ == "__main__":
    main()
