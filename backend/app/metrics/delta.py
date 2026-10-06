"""Comparison table: treatment vs baseline, aggregate and per query.

If no baseline run exists for an experiment every delta is ``None`` and the
payload carries ``baseline_missing=true``; callers render "无法比较" rather
than reporting an invented improvement.
"""
from __future__ import annotations

import psycopg

from .. import repo
from .evaluator import delta

_METRIC_KEYS = ("ndcg_at_10", "mrr_at_10", "recall_at_100", "judged_at_10")


def _metric_rows(conn: psycopg.Connection, experiment_id: str) -> dict[str, list[dict]]:
    rows = repo.fetchall(
        conn,
        "SELECT * FROM run_metrics WHERE experiment_id=%s ORDER BY query_id NULLS LAST",
        (experiment_id,),
    )
    by_role: dict[str, list[dict]] = {}
    for r in rows:
        by_role.setdefault(r["role"], []).append(r)
    return by_role


def experiment_summary(conn: psycopg.Connection, experiment_id: str) -> dict:
    exp = repo.fetchone(
        conn, "SELECT * FROM experiments WHERE experiment_id=%s", (experiment_id,)
    )
    if not exp:
        raise ValueError("experiment not found")
    roles = {r["role"] for r in repo.fetchall(
        conn, "SELECT role FROM runs WHERE experiment_id=%s", (experiment_id,)
    )}
    has_baseline = "baseline" in roles

    agg = {}
    for role in roles:
        m = repo.fetchone(
            conn,
            "SELECT * FROM run_metrics_aggregate WHERE experiment_id=%s AND role=%s",
            (experiment_id, role),
        )
        agg[role] = {k: (m[k] if m else None) for k in _METRIC_KEYS}

    aggregate_deltas = None
    if has_baseline:
        aggregate_deltas = {
            k: delta(agg.get("treatment", {}).get(k), agg.get("baseline", {}).get(k))
            for k in _METRIC_KEYS
        }

    return {
        "experiment": exp,
        "roles": sorted(roles),
        "has_baseline": has_baseline,
        "baseline_missing": not has_baseline,
        "aggregate": agg,
        "aggregate_deltas": aggregate_deltas,
    }


def comparison_table(conn: psycopg.Connection, experiment_id: str) -> dict:
    summary = experiment_summary(conn, experiment_id)
    perq = _metric_rows(conn, experiment_id)

    treatment = {r["query_id"]: r for r in perq.get("treatment", []) if r["query_id"]}
    baseline = {r["query_id"]: r for r in perq.get("baseline", []) if r["query_id"]}

    queries = repo.fetchall(conn, "SELECT * FROM queries ORDER BY query_id")
    table = []
    for q in queries:
        qid = q["query_id"]
        t, b = treatment.get(qid), baseline.get(qid)
        row = {
            "query_id": qid,
            "title": q.get("title"),
            "scenario": q.get("scenario"),
            "note": q.get("note"),
            "treatment": {k: (t[k] if t else None) for k in _METRIC_KEYS} | {
                "num_relevant": t["num_relevant"] if t else None,
                "num_returned": t["num_returned"] if t else None,
                "duplicates_dropped": t["duplicates_dropped"] if t else None,
            },
        }
        row["baseline"] = (
            {k: (b[k] if b else None) for k in _METRIC_KEYS} | {
                "num_relevant": b["num_relevant"] if b else None,
                "num_returned": b["num_returned"] if b else None,
                "duplicates_dropped": b["duplicates_dropped"] if b else None,
            }
            if b else None
        )
        if summary["has_baseline"] and b and t:
            row["deltas"] = {k: delta(t[k], b[k]) for k in _METRIC_KEYS}
        else:
            # No baseline (or it lacks this query): never invent a number.
            row["deltas"] = None
        table.append(row)

    summary["per_query"] = table
    return summary
