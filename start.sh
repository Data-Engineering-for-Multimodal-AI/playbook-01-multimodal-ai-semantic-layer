#!/bin/bash

# Granite Lite Startup Script

echo "=== Granite Lite Semantic Layer ==="
echo ""

# Check if data is set up
if [ ! -f "data/processed/granite_lite.db" ]; then
    echo "Setting up data and running ingestion..."
    python main.py --setup
    echo ""
fi

echo "Starting Granite Lite API server..."
echo "Server will be available at: http://localhost:8000"
echo "Reviewer UI: http://localhost:8000/reviewer/enc_00001"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python main.py --server
