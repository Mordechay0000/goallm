#!/bin/bash
# Run FastAPI CRM server. Auto-activates venv if it exists.

cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
export PYTHONPATH="${PYTHONPATH}:$ROOT"

# Use venv if it exists (venv or .venv)
if [ -f "$ROOT/venv/bin/activate" ]; then
  source "$ROOT/venv/bin/activate"
elif [ -f "$ROOT/.venv/bin/activate" ]; then
  source "$ROOT/.venv/bin/activate"
fi

# Check uvicorn available
if ! command -v uvicorn &>/dev/null; then
  echo "Error: uvicorn not found."
  echo ""
  echo "Run first-time setup from project root:"
  echo "  cd $ROOT"
  echo "  python3 -m venv venv"
  echo "  source venv/bin/activate"
  echo "  pip install -r requirements.txt"
  echo ""
  exit 1
fi

echo "=========================================="
echo "Starting FastAPI CRM Server"
echo "=========================================="
echo ""
echo "Backend API: http://0.0.0.0:8000 (accessible from network)"
echo "API Docs: http://0.0.0.0:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn crm.main:app --host 0.0.0.0 --port 8000 --reload
