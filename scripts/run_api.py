#!/usr/bin/env python3
"""
Run the Ads Budget Optimizer API server.

Usage:
    python scripts/run_api.py
    python scripts/run_api.py --host 0.0.0.0 --port 8000
    
Note: If using a virtual environment, activate it first:
    source .venv/bin/activate
    python scripts/run_api.py
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import uvicorn
    from src.bandit_ads.api.main import app
except ImportError as e:
    print(f"Error: {e}")
    print("\nFastAPI is not installed. Please install dependencies:")
    print("  pip install -r requirements.txt")
    print("\nOr if using a virtual environment:")
    print("  source .venv/bin/activate")
    print("  pip install -r requirements.txt")
    sys.exit(1)


def main():
    """Run the API server."""
    parser = argparse.ArgumentParser(description="Run Ads Budget Optimizer API")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    args = parser.parse_args()
    
    print(f"Starting Ads Budget Optimizer API on http://{args.host}:{args.port}")
    print(f"API docs available at http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
