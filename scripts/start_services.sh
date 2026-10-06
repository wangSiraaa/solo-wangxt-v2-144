#!/usr/bin/env bash
# Start the local PostgreSQL cluster and single-node OpenSearch used by the
# eval stack. Idempotent: safe to run when they are already up.
#
# This environment has no root/Docker, so we use a user-local conda env
# (micromamba) for PostgreSQL and the OpenSearch tarball that bundles its own
# JDK. Adjust the *_HOME variables for another machine.
set -euo pipefail

ENV_PREFIX="${ENV_PREFIX:-/home/node/envs/ir}"
PGDATA="${PGDATA:-/home/node/pgdata}"
OS_HOME="${OS_HOME:-/home/node/opensearch-2.19.1}"
OS_DATA="${OS_DATA:-/home/node/osdata}"
export PATH="$ENV_PREFIX/bin:$PATH"

# ---- PostgreSQL ----
if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
  if [ ! -s "$PGDATA/PG_VERSION" ]; then
    initdb -D "$PGDATA" -U ir --auth=trust -E UTF8 --locale=C
    cat >> "$PGDATA/postgresql.conf" <<EOF
port = 5432
listen_addresses = '127.0.0.1'
unix_socket_directories = '/tmp'
EOF
  fi
  pg_ctl -D "$PGDATA" -l /home/node/pg.log start
  sleep 2
  psql -h 127.0.0.1 -U ir -tc "SELECT 1 FROM pg_database WHERE datname='ireval'" | grep -q 1 \
    || createdb -h 127.0.0.1 -U ir ireval
  echo "PostgreSQL started."
else
  echo "PostgreSQL already running."
fi

# ---- OpenSearch ----
if ! curl -sf http://127.0.0.1:9200/ >/dev/null 2>&1; then
  if [ ! -d "$OS_HOME" ]; then
    echo "OpenSearch not found at $OS_HOME; download and extract it first:" >&2
    echo "  curl -L -o /tmp/os.tar.gz https://artifacts.opensearch.org/releases/bundle/opensearch/2.19.1/opensearch-2.19.1-linux-arm64.tar.gz" >&2
    exit 1
  fi
  grep -q "plugins.security.disabled" "$OS_HOME/config/opensearch.yml" || cat >> "$OS_HOME/config/opensearch.yml" <<EOF
discovery.type: single-node
network.host: 127.0.0.1
http.port: 9200
plugins.security.disabled: true
EOF
  mkdir -p "$OS_DATA"
  export JAVA_HOME="$OS_HOME/jdk" OPENSEARCH_JAVA_HOME="$OS_HOME/jdk"
  nohup "$OS_HOME/bin/opensearch" -E path.data="$OS_DATA" \
      -p /home/node/os.pid > /home/node/os.log 2>&1 &
  echo "Starting OpenSearch (takes ~30-60s on first run)..."
  for i in $(seq 1 40); do
    curl -sf http://127.0.0.1:9200/ >/dev/null 2>&1 && { echo "OpenSearch started."; break; }
    sleep 2
  done
else
  echo "OpenSearch already running."
fi
