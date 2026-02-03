#!/bin/bash
# First-time setup after git clone. Run from project root.

set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "=========================================="
echo "Goallm - First-time setup"
echo "=========================================="
echo ""

# Python venv
echo "1. Creating Python venv..."
python3 -m venv venv
source venv/bin/activate

echo "2. Installing Python dependencies..."
pip install -r requirements.txt

echo "3. Installing frontend dependencies..."
cd crm/frontend && npm install && cd "$ROOT"

echo "4. Creating .storage directory (databases, uploads)..."
mkdir -p "$ROOT/.storage" && chmod 755 "$ROOT/.storage"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "To run the project:"
echo "  Terminal 1 (proxy):    cd $ROOT && source venv/bin/activate && mitmproxy -s core/proxy/mitmproxy_addon.py"
echo "  Terminal 2 (backend):  cd $ROOT/crm && bash run_fastapi.sh"
echo "  Terminal 3 (frontend): cd $ROOT/crm/frontend && bash run_dev.sh"
echo ""
