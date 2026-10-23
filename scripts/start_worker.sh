#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
export PYTHONPATH="$DIR/..:$DIR/../apps/api"

echo "Starting Ghost-User Test Execution Worker..."
"$DIR/../.venv/bin/python" "$DIR/../apps/worker/worker.py"
