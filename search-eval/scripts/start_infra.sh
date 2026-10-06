#!/usr/bin/env bash
# Start local PostgreSQL 17 and OpenSearch 2.13 (user-space, no root needed).
# Idempotent: safe to re-run.
set -euo pipefail

INFRA=/workspace/.infra
PGDATA=$INFRA/pgdata
OS=$INFRA/opensearch
export PATH="$INFRA/postgres/bin:$PATH"

# --- PostgreSQL ---
if [ ! -d "$PGDATA" ]; then
  initdb -D "$PGDATA" -U "$(whoami)" --auth=trust -E UTF8
fi
mkdir -p /tmp/pgsock   # virtiofs cannot host unix sockets
if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -l "$INFRA/pg.log" -o "-p 5432 -k /tmp/pgsock" start
fi
python3 - <<'EOF' || true
import psycopg
c = psycopg.connect('host=localhost port=5432 user=' + __import__('getpass').getuser()
                    + ' dbname=postgres', autocommit=True)
c.execute('CREATE DATABASE searcheval')
print('database searcheval created')
EOF

# --- OpenSearch ---
if ! curl -sf localhost:9200/_cluster/health >/dev/null 2>&1; then
  if [ ! -x "$OS/bin/opensearch" ]; then
    echo "OpenSearch not found at $OS - see README (download step)" >&2
    exit 1
  fi
  nohup "$OS/bin/opensearch" > "$INFRA/opensearch.log" 2>&1 &
  for i in $(seq 1 40); do
    sleep 3
    curl -sf localhost:9200/_cluster/health >/dev/null 2>&1 && break
  done
fi
echo "infra ready: postgres@5432, opensearch@9200"
