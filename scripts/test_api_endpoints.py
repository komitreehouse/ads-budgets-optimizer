#!/usr/bin/env python3
"""
Test API endpoints with real data.

Tests the API endpoints by calling them directly (without starting a server).
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from src.bandit_ads.api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    print("Testing /api/health...")
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    print(f"  ✅ Status: {data['status']}")
    print(f"  ✅ Database: {data['database']}")
    return True


def test_campaigns_endpoint():
    """Test campaigns list endpoint."""
    print("\nTesting /api/campaigns...")
    response = client.get("/api/campaigns")
    assert response.status_code == 200
    campaigns = response.json()
    print(f"  ✅ Found {len(campaigns)} campaigns")
    if campaigns:
        print(f"  ✅ First campaign: {campaigns[0]['name']}")
    return True


def test_campaign_detail():
    """Test campaign detail endpoint."""
    print("\nTesting /api/campaigns/1...")
    response = client.get("/api/campaigns/1")
    if response.status_code == 404:
        print("  ⚠️  Campaign 1 not found (this is OK if no data)")
        return True
    assert response.status_code == 200
    campaign = response.json()
    print(f"  ✅ Campaign: {campaign['name']}")
    print(f"  ✅ ROAS: {campaign['roas']:.2f}")
    return True


def test_dashboard_summary():
    """Test dashboard summary endpoint."""
    print("\nTesting /api/dashboard/summary...")
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    print(f"  ✅ Total spend today: ${data['total_spend_today']:.2f}")
    print(f"  ✅ Active campaigns: {data['active_campaigns']}")
    return True


def test_campaign_metrics():
    """Test campaign metrics endpoint."""
    print("\nTesting /api/campaigns/1/metrics...")
    response = client.get("/api/campaigns/1/metrics?time_range=7D")
    if response.status_code == 404:
        print("  ⚠️  Campaign 1 not found (this is OK if no data)")
        return True
    assert response.status_code == 200
    metrics = response.json()
    print(f"  ✅ Impressions: {metrics['impressions']}")
    print(f"  ✅ ROAS: {metrics['roas']:.2f}")
    return True


def main():
    """Run all endpoint tests."""
    print("=" * 60)
    print("Testing API Endpoints")
    print("=" * 60)
    
    tests = [
        ("Health Check", test_health_endpoint),
        ("Campaigns List", test_campaigns_endpoint),
        ("Campaign Detail", test_campaign_detail),
        ("Dashboard Summary", test_dashboard_summary),
        ("Campaign Metrics", test_campaign_metrics),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✅ All endpoint tests passed!")
        print("\nYou can now start the API server:")
        print("  source .venv/bin/activate")
        print("  python scripts/run_api.py")
    else:
        print("\n⚠️  Some tests failed.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
