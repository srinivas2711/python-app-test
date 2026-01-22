#!/bin/bash
set -e

echo "Starting Azure Web App..."

# Install dependencies
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Starting Gunicorn..."
exec gunicorn app.main:app \
     --bind 0.0.0.0:${PORT:-8000} \
     --workers 2
