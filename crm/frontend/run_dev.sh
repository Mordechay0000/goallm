#!/bin/bash
# Run Vite dev server. Auto-runs npm install if node_modules missing.

cd "$(dirname "$0")"

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies (npm install)..."
  npm install || { echo "Error: npm install failed. Is Node.js installed?"; exit 1; }
fi

echo "Starting Vite dev server..."
npm run dev
