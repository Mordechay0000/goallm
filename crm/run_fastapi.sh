#!/bin/bash
# Run FastAPI CRM server

cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."

echo "=========================================="
echo "Starting FastAPI CRM Server"
echo "=========================================="
echo ""
echo "Backend API: http://127.0.0.1:8000"
echo "API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn crm.main:app --host 127.0.0.1 --port 8000 --reload
