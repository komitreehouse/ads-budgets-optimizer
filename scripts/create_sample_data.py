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
from src.bandit_ads.db_helpers import (
    create_campaign, create_arm, create_metric
)
from src.bandit_ads.models import (
    CampaignCreate, ArmCreate, MetricCreate
)


def create_sample_campaigns():
    """Create sample campaigns."""
    print("Creating sample campaigns...")
    
    campaigns_data = [
        {
            "name": "Q1 Brand Awareness",
            "budget": 50000.0,
            "start_date": datetime.utcnow() - timedelta(days=30),
            "status": "active"
        },
        {
            "name": "Product Launch - Widget X",
            "budget": 30000.0,
            "start_date": datetime.utcnow() - timedelta(days=15),
            "status": "active"
        },
        {
            "name": "Retargeting Campaign",
            "budget": 20000.0,
            "start_date": datetime.utcnow() - timedelta(days=60),
            "status": "paused"
        },
        {
            "name": "Holiday Promotions",
            "budget": 45000.0,
            "start_date": datetime.utcnow() - timedelta(days=7),
            "status": "active"
        },
        {
            "name": "Summer Sale",
            "budget": 35000.0,
            "start_date": datetime.utcnow() - timedelta(days=90),
            "end_date": datetime.utcnow() - timedelta(days=30),
            "status": "completed"
        }
    ]
    
    campaigns = []
    for data in campaigns_data:
        campaign_data = CampaignCreate(**data)
        campaign = create_campaign(campaign_data)
        campaigns.append(campaign)
        print(f"  ✓ Created campaign: {campaign.name} (ID: {campaign.id})")
    
    return campaigns


def create_sample_arms(campaigns):
    """Create sample arms for campaigns."""
    print("\nCreating sample arms...")
    
    platforms = ["Google", "Meta", "The Trade Desk"]
    channels = ["Search", "Display", "Social"]
    creatives = ["Creative A", "Creative B", "Creative C"]
    bids = [1.0, 1.5, 2.0, 2.5]
    
    all_arms = []
    
    for campaign in campaigns:
        # Create 3-5 arms per campaign
        num_arms = random.randint(3, 5)
        selected_combos = random.sample(
            [(p, c, cr, b) for p in platforms for c in channels for cr in creatives for b in bids],
            num_arms
        )
        
        for platform, channel, creative, bid in selected_combos:
            arm_data = ArmCreate(
                campaign_id=campaign.id,
                platform=platform,
                channel=channel,
                creative=creative,
                bid=bid,
                platform_entity_ids={
                    "campaign_id": f"{platform.lower()}_{campaign.id}",
                    "ad_group_id": f"ag_{random.randint(1000, 9999)}"
                }
            )
            arm = create_arm(arm_data)
            all_arms.append((campaign.id, arm))
            print(f"  ✓ Created arm: {platform}/{channel}/{creative} (Bid: ${bid})")
    
    return all_arms


def create_sample_metrics(campaigns, arms):
    """Create sample metrics for the past 30 days."""
    print("\nCreating sample metrics...")
    
    db_manager = get_db_manager()
    
    # Create metrics for the past 30 days
    for day_offset in range(30):
        date = datetime.utcnow() - timedelta(days=day_offset)
        
        for campaign_id, arm in arms:
            # Skip if campaign is completed and date is after end date
            campaign = next((c for c in campaigns if c.id == campaign_id), None)
            if campaign and campaign.end_date and date > campaign.end_date:
                continue
            
            # Generate realistic metrics
            base_impressions = random.randint(1000, 10000)
            ctr = random.uniform(0.02, 0.08)
            cvr = random.uniform(0.05, 0.15)
            cpc = random.uniform(0.5, 2.0)
            revenue_per_conversion = random.uniform(10.0, 50.0)
            
            impressions = int(base_impressions * random.uniform(0.8, 1.2))
            clicks = int(impressions * ctr)
            conversions = int(clicks * cvr)
            cost = clicks * cpc
            revenue = conversions * revenue_per_conversion
            roas = revenue / cost if cost > 0 else 0.0
            
            metric_data = MetricCreate(
                campaign_id=campaign_id,
                arm_id=arm.id,
                timestamp=date,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                revenue=revenue,
                cost=cost,
                roas=roas,
                source="simulated"
            )
            
            create_metric(metric_data)
        
        if day_offset % 5 == 0:
            print(f"  ✓ Created metrics for day {day_offset + 1}/30")
    
    print("  ✓ All metrics created")


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
    print(f"\nCreated:")
    print(f"  - {len(campaigns)} campaigns")
    print(f"  - {len(arms)} arms")
    print(f"  - ~{len(arms) * 30} metric records (30 days)")
    print("\nYou can now:")
    print("  1. Start the API: python3 scripts/run_api.py")
    print("  2. Start the frontend: streamlit run frontend/app.py")
    print("  3. View the data in the dashboard!")


if __name__ == "__main__":
    main()
