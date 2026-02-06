#!/bin/bash
# Start the Streamlit frontend server

echo "🚀 Starting Ads Budget Optimizer Frontend..."
echo ""
echo "The dashboard will open in your browser at:"
echo "   http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd "$(dirname "$0")/.."
streamlit run frontend/app.py --server.port 8501
