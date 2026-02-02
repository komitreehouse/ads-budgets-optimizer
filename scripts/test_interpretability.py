"""
Test script for the Interpretability Layer.

This demonstrates:
1. Running optimization cycles with change tracking
2. Generating LLM-powered explanations
3. Using the orchestrator for natural language queries
4. Creating and explaining recommendations

Usage:
    python scripts/test_interpretability.py

Requirements:
    - Set ANTHROPIC_API_KEY environment variable for LLM explanations
    - Or run without it for template-based explanations (still works!)
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config
from src.bandit_ads.utils import ConfigManager, get_logger
from src.bandit_ads.database import get_db_manager, Campaign, Arm, Metric
from src.bandit_ads.change_tracker import get_change_tracker
from src.bandit_ads.explanation_generator import get_explanation_generator
from src.bandit_ads.recommendations import get_recommendation_manager

logger = get_logger('test_interpretability')


def setup_test_data():
    """Set up test campaign data in database."""
    print("\n" + "=" * 70)
    print("Step 1: Setting up test data")
    print("=" * 70)
    
    db_manager = get_db_manager()
    
    # Ensure all tables are created
    from src.bandit_ads.database import Base
    from src.bandit_ads.change_tracker import AllocationChange, DecisionLog
    from src.bandit_ads.recommendations import Recommendation
    Base.metadata.create_all(db_manager.engine)
    print("✓ Database tables created/verified")
    
    with db_manager.get_session() as session:
        # Create or get test campaign
        campaign = session.query(Campaign).filter(Campaign.name == "Test Campaign").first()
        if not campaign:
            campaign = Campaign(
                name="Test Campaign",
                budget=10000.0,
                start_date=datetime.utcnow(),
                status="active"
            )
            session.add(campaign)
            session.commit()
            print(f"✓ Created campaign: {campaign.name} (ID: {campaign.id})")
        else:
            print(f"✓ Using existing campaign: {campaign.name} (ID: {campaign.id})")
        
        campaign_id = campaign.id
        
        # Create arms if they don't exist
        arms_data = [
            {"platform": "Google", "channel": "Search", "creative": "Creative A", "bid": 1.0},
            {"platform": "Google", "channel": "Display", "creative": "Creative A", "bid": 1.0},
            {"platform": "Meta", "channel": "Social", "creative": "Creative B", "bid": 1.5},
            {"platform": "The Trade Desk", "channel": "Display", "creative": "Creative A", "bid": 2.0},
        ]
        
        arm_ids = []
        for arm_data in arms_data:
            arm = session.query(Arm).filter(
                Arm.campaign_id == campaign_id,
                Arm.platform == arm_data["platform"],
                Arm.channel == arm_data["channel"]
            ).first()
            
            if not arm:
                arm = Arm(
                    campaign_id=campaign_id,
                    platform=arm_data["platform"],
                    channel=arm_data["channel"],
                    creative=arm_data["creative"],
                    bid=arm_data["bid"]
                )
                session.add(arm)
                session.commit()
                print(f"  ✓ Created arm: {arm.platform}/{arm.channel}")
            else:
                print(f"  ✓ Using existing arm: {arm.platform}/{arm.channel}")
            
            arm_ids.append(arm.id)
        
        # Add some mock metrics
        print("\nAdding mock performance metrics...")
        base_date = datetime.utcnow() - timedelta(days=7)
        
        for day in range(7):
            metric_date = base_date + timedelta(days=day)
            for i, arm_id in enumerate(arm_ids):
                # Simulate different performance per arm
                base_impressions = 1000 + (i * 200)
                base_ctr = 0.05 + (i * 0.01)
                base_cvr = 0.10 + (i * 0.02)
                
                impressions = int(base_impressions * (1 + day * 0.05))  # Growing
                clicks = int(impressions * base_ctr)
                conversions = int(clicks * base_cvr)
                cost = clicks * (1.0 + i * 0.2)
                revenue = conversions * 15.0
                
                metric = Metric(
                    campaign_id=campaign_id,
                    arm_id=arm_id,
                    timestamp=metric_date,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    cost=cost,
                    revenue=revenue,
                    roas=revenue / cost if cost > 0 else 0
                )
                session.add(metric)
        
        session.commit()
        print(f"  ✓ Added metrics for {len(arm_ids)} arms over 7 days")
    
    return campaign_id, arm_ids


def simulate_allocation_changes(campaign_id: int, arm_ids: list):
    """Simulate some allocation changes to test explanations."""
    print("\n" + "=" * 70)
    print("Step 2: Simulating allocation changes")
    print("=" * 70)
    
    change_tracker = get_change_tracker()
    
    # Simulate optimizer making changes
    changes = [
        {
            "arm_id": arm_ids[0],
            "old_allocation": 0.25,
            "new_allocation": 0.35,
            "change_type": "optimizer_decision",
            "reason": "High ROAS performance detected",
            "factors": {"roas_improvement": 0.15, "low_variance": True},
            "mmm_factors": {"seasonality": 0.1, "carryover": 0.05}
        },
        {
            "arm_id": arm_ids[1],
            "old_allocation": 0.25,
            "new_allocation": 0.20,
            "change_type": "optimizer_decision",
            "reason": "Lower CTR compared to alternatives",
            "factors": {"ctr_decline": -0.02, "market_saturation": 0.1},
            "mmm_factors": {"competition": 0.08}
        },
        {
            "arm_id": arm_ids[2],
            "old_allocation": 0.25,
            "new_allocation": 0.30,
            "change_type": "manual_override",
            "reason": "Analyst requested increase for new product launch",
            "factors": {"analyst_override": True, "product_launch": "New Widget X"},
            "mmm_factors": {}
        },
    ]
    
    change_ids = []
    for change_data in changes:
        change = change_tracker.log_allocation_change(
            campaign_id=campaign_id,
            arm_id=change_data["arm_id"],
            old_allocation=change_data["old_allocation"],
            new_allocation=change_data["new_allocation"],
            change_type=change_data["change_type"],
            change_reason=change_data["reason"],
            factors=change_data["factors"],
            mmm_factors=change_data["mmm_factors"]
        )
        change_id = change.id if change else None
        change_ids.append(change_id)
        print(f"  ✓ Logged change {change_id}: {change_data['reason'][:50]}...")
    
    return change_ids


async def test_explanation_generation(change_ids: list, campaign_id: int):
    """Test LLM-powered explanation generation."""
    print("\n" + "=" * 70)
    print("Step 3: Testing Explanation Generation")
    print("=" * 70)
    
    explanation_generator = get_explanation_generator()
    
    # Check if LLM is available
    if explanation_generator.claude_client:
        print("✓ Claude API available - using LLM-powered explanations")
    else:
        print("⚠ Claude API not available - using template-based explanations")
        print("  (Set ANTHROPIC_API_KEY for LLM-powered explanations)")
    
    # Test allocation change explanation
    print("\n--- Allocation Change Explanation ---")
    if change_ids:
        explanation = await explanation_generator.explain_allocation_change(
            change_id=change_ids[0],
            include_historical_context=True
        )
        print(explanation)
    
    # Test performance explanation
    print("\n--- Performance Explanation ---")
    explanation = await explanation_generator.explain_performance(
        campaign_id=campaign_id,
        time_range="7d",
        include_trends=True
    )
    print(explanation)


async def test_recommendations(campaign_id: int, arm_ids: list):
    """Test recommendation system with explanations."""
    print("\n" + "=" * 70)
    print("Step 4: Testing Recommendation System")
    print("=" * 70)
    
    recommendation_manager = get_recommendation_manager()
    explanation_generator = get_explanation_generator()
    
    # Create a test recommendation
    from src.bandit_ads.recommendations import Recommendation
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        import json
        rec = Recommendation(
            campaign_id=campaign_id,
            recommendation_type="allocation_change",
            title="Increase Google Search allocation",
            description="Based on strong ROAS performance, recommend increasing allocation by 10%",
            details=json.dumps({
                "arm_id": arm_ids[0],
                "current_allocation": 0.25, 
                "suggested_allocation": 0.35, 
                "expected_roas_impact": "+12%",
                "confidence_score": 0.85
            }),
            status="pending"
        )
        session.add(rec)
        session.commit()
        rec_id = rec.id
        print(f"✓ Created recommendation (ID: {rec_id})")
    
    # Explain the recommendation
    print("\n--- Recommendation Explanation ---")
    explanation = await explanation_generator.explain_recommendation(rec_id)
    print(explanation)


def test_change_history(campaign_id: int):
    """Test querying change history."""
    print("\n" + "=" * 70)
    print("Step 5: Testing Change History")
    print("=" * 70)
    
    change_tracker = get_change_tracker()
    
    # Get allocation history
    history = change_tracker.get_allocation_history(campaign_id, days=30)
    
    print(f"Found {len(history)} allocation changes in the last 30 days:")
    for change in history[:5]:  # Show first 5
        print(f"  - Arm {change.arm_id}: {change.old_allocation:.1%} → {change.new_allocation:.1%} ({change.change_type})")


async def test_orchestrator_queries(campaign_id: int):
    """Test the orchestrator with natural language queries."""
    print("\n" + "=" * 70)
    print("Step 6: Testing Orchestrator (Natural Language Queries)")
    print("=" * 70)
    
    from src.bandit_ads.orchestrator import get_orchestrator
    
    orchestrator = get_orchestrator()
    
    # Test queries
    queries = [
        f"What is the status of campaign {campaign_id}?",
        f"Explain why allocation changed for campaign {campaign_id}",
        f"How is campaign {campaign_id} performing?",
    ]
    
    for query in queries:
        print(f"\n>>> Query: {query}")
        print("-" * 50)
        
        try:
            # Note: This requires full orchestrator setup with auth
            # For testing, we'll show what would happen
            result = await orchestrator.process_query(
                query=query,
                user_id="test_user",
                campaign_id=campaign_id
            )
            print(f"Response: {result.get('response', result)[:500]}...")
        except Exception as e:
            print(f"(Orchestrator requires full setup - showing query routing instead)")
            from src.bandit_ads.llm_router import get_llm_router
            router = get_llm_router()
            query_type = router.classify_query(query)
            print(f"Query type: {query_type.value}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("INTERPRETABILITY LAYER TEST")
    print("=" * 70)
    print(f"\nTimestamp: {datetime.now().isoformat()}")
    print("This script tests the explanation generation and interpretability features.")
    
    # Check for API key
    if os.getenv("ANTHROPIC_API_KEY"):
        print("✓ ANTHROPIC_API_KEY is set - LLM explanations enabled")
    else:
        print("⚠ ANTHROPIC_API_KEY not set - will use template explanations")
        print("  Set the key for full LLM-powered explanations")
    
    try:
        # Setup
        campaign_id, arm_ids = setup_test_data()
        
        # Simulate changes
        change_ids = simulate_allocation_changes(campaign_id, arm_ids)
        
        # Test explanations
        await test_explanation_generation(change_ids, campaign_id)
        
        # Test recommendations
        await test_recommendations(campaign_id, arm_ids)
        
        # Test history
        test_change_history(campaign_id)
        
        # Test orchestrator
        await test_orchestrator_queries(campaign_id)
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 70)
        print("\nSummary:")
        print(f"  - Campaign ID: {campaign_id}")
        print(f"  - Arms created: {len(arm_ids)}")
        print(f"  - Changes logged: {len(change_ids)}")
        print("\nNext steps:")
        print("  1. Set ANTHROPIC_API_KEY for LLM-powered explanations")
        print("  2. Run the MCP server for tool-based interactions")
        print("  3. Use the orchestrator for natural language queries")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
