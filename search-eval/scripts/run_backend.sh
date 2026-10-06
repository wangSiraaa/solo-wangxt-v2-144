#!/usr/bin/env bash
# Run the FastAPI backend (serves API + built frontend on :8000).
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
