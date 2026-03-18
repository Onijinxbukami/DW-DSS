#!/bin/bash
# setup.sh – One-time database setup from CSV files
# Usage: bash setup.sh

set -e
echo "=== DW-DSS Setup ==="

echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "[2/3] Running ETL pipeline (builds Star Schema from CSV)..."
python etl/run_etl.py

echo "[3/3] Building data mart (2024-12-31 snapshot)..."
python mart/build_mart.py 2024-12-31

echo ""
echo "=== Setup complete ==="
echo "Run: python run.py"
echo "Open: http://localhost:5000"
