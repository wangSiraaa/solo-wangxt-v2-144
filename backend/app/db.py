"""Connection management for PostgreSQL and OpenSearch.

Connections are created lazily and reused. The local OpenSearch node has the
security plugin disabled, so no credentials are needed.
"""
from __future__ import annotations

import functools

import psycopg
from opensearchpy import OpenSearch

from .config import settings


@functools.cache
def pg_conninfo() -> str:
    return settings.database_url


def get_db() -> psycopg.Connection:
    """FastAPI dependency: one connection per request."""
    conn = psycopg.connect(pg_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


@functools.lru_cache(maxsize=1)
def get_os_client() -> OpenSearch:
    hosts = [h.strip() for h in settings.opensearch_hosts.split(",") if h.strip()]
    return OpenSearch(
        hosts=hosts,
        http_compress=True,
        verify_certs=settings.opensearch_verify_certs,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )
