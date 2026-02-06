#!/usr/bin/env python3
"""
Start the Streamlit frontend server.
"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    """Start the Streamlit frontend."""
    project_root = Path(__file__).parent.parent
    
    print("🚀 Starting Ads Budget Optimizer Frontend...")
    print("")
    print("The dashboard will open in your browser at:")
    print("   http://localhost:8501")
    print("")
    print("Press Ctrl+C to stop the server")
    print("")
    
    # Change to project root
    os.chdir(project_root)
    
    # Run streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "frontend/app.py",
            "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped.")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("\nTry running manually:")
        print("  streamlit run frontend/app.py --server.port 8501")
        sys.exit(1)

if __name__ == "__main__":
    main()
