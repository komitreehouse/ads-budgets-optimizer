#!/usr/bin/env python3
"""
Check if FastAPI and other dependencies are installed correctly.
"""

import sys

def check_package(package_name, import_name=None):
    """Check if a package is installed."""
    if import_name is None:
        import_name = package_name
    
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {package_name}: {version}")
        return True
    except ImportError:
        print(f"❌ {package_name}: NOT INSTALLED")
        return False

def main():
    """Check all required packages."""
    print("=" * 60)
    print("Checking Python Environment")
    print("=" * 60)
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path[0]}")
    print()
    
    print("=" * 60)
    print("Checking Required Packages")
    print("=" * 60)
    
    packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("sqlalchemy", "sqlalchemy"),
        ("pydantic", "pydantic"),
        ("flask", "flask"),
        ("apscheduler", "apscheduler"),
    ]
    
    results = []
    for package_name, import_name in packages:
        results.append(check_package(package_name, import_name))
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    if all(results):
        print("✅ All required packages are installed!")
        print("\nYou can now:")
        print("  1. Run tests: python3 scripts/test_api.py")
        print("  2. Start API: python3 scripts/run_api.py")
    else:
        print("⚠️  Some packages are missing.")
        print("\nTo install missing packages:")
        print("  pip3 install -r requirements.txt")
        print("\nOr install individually:")
        missing = [p[0] for p, r in zip(packages, results) if not r]
        print(f"  pip3 install {' '.join(missing)}")
    
    return 0 if all(results) else 1

if __name__ == "__main__":
    sys.exit(main())
