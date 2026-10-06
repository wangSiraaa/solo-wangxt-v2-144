#!/usr/bin/env bash
# Build the Vue 3 frontend into frontend/dist (served by the backend).
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm install --no-audit --no-fund
./node_modules/.bin/vite build
