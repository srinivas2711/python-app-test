#!/bin/bash
set -e

echo "Starting Flask app..."

pip install --no-cache-dir -r requirements.txt

exec gunicorn app.main:app \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 2 \
  --timeout 600
