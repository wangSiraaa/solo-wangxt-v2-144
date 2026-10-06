"""Thin data-access helpers for PostgreSQL."""
from __future__ import annotations

import json
from typing import Any

import psycopg


def fetchall(conn: psycopg.Connection, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetchone(conn: psycopg.Connection, sql: str, params: tuple = ()) -> dict | None:
    rows = fetchall(conn, sql, params)
    return rows[0] if rows else None


def load_qrels(conn: psycopg.Connection, set_id: str) -> dict[str, dict[str, int]]:
    rows = fetchall(
        conn,
        "SELECT query_id, canonical_doc_id, grade FROM qrels WHERE set_id = %s",
        (set_id,),
    )
    qrels: dict[str, dict[str, int]] = {}
    for r in rows:
        qrels.setdefault(r["query_id"], {})[r["canonical_doc_id"]] = int(r["grade"])
    # queries with no qrel rows still need an empty dict entry
    for r in fetchall(conn, "SELECT query_id FROM queries"):
        qrels.setdefault(r["query_id"], {})
    return qrels


def load_run_config(conn: psycopg.Connection, config_id: str) -> dict:
    return fetchone(conn, "SELECT config_id, config FROM run_configs WHERE config_id=%s",
                    (config_id,))


def experiment_exists(conn: psycopg.Connection, experiment_id: str) -> bool:
    return fetchone(conn, "SELECT 1 FROM experiments WHERE experiment_id=%s",
                    (experiment_id,)) is not None


def save_experiment(
    conn: psycopg.Connection,
    exp: dict,
    index_snapshots: dict[str, Any],
    *,
    replace: bool = False,
) -> None:
    if replace:
        # Manual cascade: run_* tables reference runs, which references
        # experiments, without ON DELETE CASCADE on every link.
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM run_metrics_aggregate WHERE experiment_id=%s",
                (exp["experiment_id"],),
            )
            cur.execute(
                "DELETE FROM run_metrics WHERE experiment_id=%s",
                (exp["experiment_id"],),
            )
            cur.execute(
                "DELETE FROM run_rankings WHERE experiment_id=%s",
                (exp["experiment_id"],),
            )
            cur.execute(
                "DELETE FROM runs WHERE experiment_id=%s", (exp["experiment_id"],)
            )
            cur.execute(
                "DELETE FROM experiments WHERE experiment_id=%s",
                (exp["experiment_id"],),
            )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO experiments
              (experiment_id, name, description, judgment_set_id,
               treatment_config_id, baseline_config_id, index_name,
               index_settings_snapshot, index_mapping_snapshot)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                exp["experiment_id"], exp["name"], exp["description"],
                exp["judgment_set_id"], exp["treatment_config_id"],
                exp["baseline_config_id"], index_snapshots["index"],
                json.dumps(index_snapshots.get("settings_snapshot")),
                json.dumps(index_snapshots.get("mapping_snapshot")),
            ),
        )


def save_run(
    conn: psycopg.Connection,
    experiment_id: str,
    role: str,
    config_id: str,
    index_name: str,
    config: dict,
    rankings: dict[str, list[dict]],
    metrics: dict,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO runs (experiment_id, config_id, role, index_name, run_config_snapshot)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (experiment_id, config_id, role, index_name, json.dumps(config)),
        )
        for query_id, hits in rankings.items():
            for h in hits:
                cur.execute(
                    """
                    INSERT INTO run_rankings
                      (experiment_id, role, query_id, rank, raw_rank, doc_id,
                       canonical_doc_id, score, tied, duplicate)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (experiment_id, role, query_id, h["rank"], h.get("raw_rank"),
                     h["doc_id"], h["canonical_id"], h["score"],
                     h.get("tied", False), h.get("duplicate", False)),
                )
        cur.execute(
            """
            INSERT INTO run_metrics_aggregate
              (experiment_id, role, ndcg_at_10, mrr_at_10, recall_at_100,
               judged_at_10, num_queries, num_zero_relevant, num_missing_run,
               num_duplicates_dropped)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                experiment_id, role,
                metrics["aggregate"]["ndcg_at_10"],
                metrics["aggregate"]["mrr_at_10"],
                metrics["aggregate"]["recall_at_100"],
                metrics["aggregate"]["judged_at_10"],
                metrics["counts"]["num_queries"],
                metrics["counts"]["num_zero_relevant_queries"],
                metrics["counts"]["num_missing_run_queries"],
                metrics["counts"]["num_duplicates_dropped"],
            ),
        )
        for pq in metrics["per_query"]:
            cur.execute(
                """
                INSERT INTO run_metrics
                  (experiment_id, role, query_id, ndcg_at_10, mrr_at_10, recall_at_100,
                   judged_at_10, ndcg_raw_zero_rel, mrr_raw_zero_rel, recall_raw_zero_rel,
                   num_relevant, num_returned, duplicates_dropped)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    experiment_id, role, pq["query_id"],
                    pq["ndcg_at_10"], pq["mrr_at_10"], pq["recall_at_100"],
                    pq["judged_at_10"], pq["ndcg_raw_zero_rel"],
                    pq["mrr_raw_zero_rel"], pq["recall_raw_zero_rel"],
                    pq["num_relevant"], pq["num_returned"], pq["duplicates_dropped"],
                ),
            )
