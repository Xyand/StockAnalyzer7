#!/usr/bin/env bash
# Start StockAnalyzer7 on http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

exec ./.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port "${PORT:-8000}" "$@"
