#!/usr/bin/env bash
# Seed the synthetic corpus, judgments and demo experiments.
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec ../.venv/bin/python -m app.seed
