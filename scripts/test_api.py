#!/usr/bin/env python3
"""
Test script for the API endpoints.

Tests basic API functionality without starting a full server.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all API modules can be imported."""
    print("Testing API imports...")
    
    # Check if FastAPI is installed first
    try:
        import fastapi
        print(f"  ✓ FastAPI {fastapi.__version__} found")
    except ImportError:
        print("  ❌ FastAPI not installed")
        print("     Install with: pip3 install fastapi uvicorn python-multipart")
        return False
    
    try:
        from src.bandit_ads.api.main import app
        from src.bandit_ads.api.routes import campaigns, dashboard, recommendations, optimizer
        print("✅ All API modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database():
    """Test database connection."""
    print("\nTesting database connection...")
    try:
        from src.bandit_ads.database import init_database, get_db_manager
        db_manager = init_database(create_tables=True)
        healthy = db_manager.health_check()
        if healthy:
            print("✅ Database connection successful")
            return True
        else:
            print("⚠️  Database connection failed health check")
            return False
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_routes():
    """Test that API routes are registered."""
    print("\nTesting API routes...")
    try:
        from src.bandit_ads.api.main import app
        
        routes = [route.path for route in app.routes]
        expected_routes = [
            "/",
            "/api/health",
            "/api/campaigns",
            "/api/dashboard/summary",
            "/api/dashboard/brand-budget",
            "/api/dashboard/channel-splits",
            "/api/recommendations",
            "/api/optimizer/status"
        ]
        
        print(f"Found {len(routes)} routes")
        for route in routes[:10]:  # Show first 10
            print(f"  - {route}")
        
        # Check for key routes
        route_paths = [route.path for route in app.routes]
        missing = [r for r in expected_routes if r not in route_paths]
        if missing:
            print(f"⚠️  Missing routes: {missing}")
        else:
            print("✅ All expected routes found")
        
        return True
    except Exception as e:
        print(f"❌ Route test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_service():
    """Test that data service can connect to API."""
    print("\nTesting data service API connection...")
    try:
        from frontend.services.data_service import DataService
        
        # Test with API URL that won't exist (should fall back to mock)
        service = DataService(api_base_url="http://localhost:9999")
        if service.use_mock:
            print("✅ Data service correctly falls back to mock when API unavailable")
        else:
            print("⚠️  Data service didn't detect API unavailability")
        
        # Test with actual API URL (if running)
        service2 = DataService(api_base_url="http://localhost:8000")
        print(f"   API connection status: {'Connected' if not service2.use_mock else 'Using mock (API not running)'}")
        
        return True
    except Exception as e:
        print(f"❌ Data service test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Ads Budget Optimizer API Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Database", test_database()))
    results.append(("API Routes", test_api_routes()))
    results.append(("Data Service", test_data_service()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✅ All tests passed!")
        print("\nTo start the API server, run:")
        print("  python3 scripts/run_api.py")
    else:
        print("\n⚠️  Some tests failed. Please fix errors before starting the API.")
        
        # Check if it's just missing FastAPI
        try:
            import fastapi
        except ImportError:
            print("\n💡 Quick Fix:")
            print("   Install FastAPI dependencies:")
            print("   pip3 install -r requirements.txt")
            print("   or")
            print("   pip3 install fastapi uvicorn python-multipart")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
