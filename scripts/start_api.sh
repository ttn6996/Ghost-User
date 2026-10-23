#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
export PYTHONPATH="$DIR/..:$DIR/../apps/api"

echo "Starting Ghost-User API Server on http://127.0.0.1:8000..."
"$DIR/../.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --reload
