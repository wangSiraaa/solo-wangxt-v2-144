#!/usr/bin/env bash
# Stop the local PostgreSQL cluster and OpenSearch node.
set -euo pipefail
PGDATA="${PGDATA:-/home/node/pgdata}"
export PATH="/home/node/envs/ir/bin:$PATH"

pg_ctl -D "$PGDATA" stop 2>/dev/null && echo "PostgreSQL stopped." || echo "PostgreSQL not running."

if [ -f /home/node/os.pid ]; then
  kill "$(cat /home/node/os.pid)" 2>/dev/null && echo "OpenSearch stopped." || echo "OpenSearch pid stale."
  rm -f /home/node/os.pid
else
  pkill -f 'opensearch.*path.data=/home/node/osdata' 2>/dev/null && echo "OpenSearch stopped." || echo "OpenSearch not running."
fi
