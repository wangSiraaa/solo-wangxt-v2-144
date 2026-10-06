"""Integration test against the *live* local stack.

Skipped unless IREVAL_RUN_INTEGRATION=1 and both Postgres and OpenSearch are
reachable and seeded (run ``python -m app.seed`` first).
"""
from __future__ import annotations

import os

import psycopg
import pytest

from app.config import settings
from app.db import get_os_client
from app.metrics.delta import comparison_table

pytestmark = pytest.mark.skipif(
    os.getenv("IREVAL_RUN_INTEGRATION") != "1",
    reason="set IREVAL_RUN_INTEGRATION=1 to run live-stack tests",
)


@pytest.fixture(scope="module")
def conn():
    c = psycopg.connect(settings.database_url)
    yield c
    c.close()


def test_opensearch_ping():
    assert get_os_client().ping()


def test_title_boost_has_both_a_helped_and_a_hurt_query(conn):
    table = comparison_table(conn, "exp-title-boost")
    assert table["has_baseline"]
    mrr_deltas = {r["query_id"]: r["deltas"]["mrr_at_10"] for r in table["per_query"]}
    assert mrr_deltas["q_publish"] > 0
    assert mrr_deltas["q_photo"] < 0


def test_zero_relevant_and_zero_hits_are_null(conn):
    table = comparison_table(conn, "exp-title-boost")
    rows = {r["query_id"]: r for r in table["per_query"]}
    for qid in ("q_keyboard", "q_quantum"):
        assert rows[qid]["treatment"]["mrr_at_10"] is None
        assert rows[qid]["treatment"]["ndcg_at_10"] is None


def test_duplicate_scenario_dropped_one_copy(conn):
    table = comparison_table(conn, "exp-title-boost")
    row = {r["query_id"]: r for r in table["per_query"]}["q_py_sort"]
    assert row["treatment"]["duplicates_dropped"] == 1


def test_missing_baseline_reports_no_deltas(conn):
    table = comparison_table(conn, "exp-strict-and-standalone")
    assert table["baseline_missing"]
    assert table["aggregate_deltas"] is None
    assert all(r["deltas"] is None for r in table["per_query"])
