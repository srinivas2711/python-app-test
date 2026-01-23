#!/bin/bash
set -e

echo "Starting Azure Web App..."

# Install dependencies
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Starting Gunicorn..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
