#!/usr/bin/env bash
set -e

echo "Starting Ghost-User Dashboard on http://localhost:3000..."
npm run dev --workspace=apps/web
