#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
export PYTHONPATH="$DIR/..:$DIR/../apps/api"
export ENVIRONMENT="test"
export DATABASE_URL="sqlite:///:memory:"
export ALLOW_LOCAL_TARGETS="true"

echo "Running Ghost-User automated test suite..."
"$DIR/../.venv/bin/pytest" -v
echo "All tests passed successfully!"
