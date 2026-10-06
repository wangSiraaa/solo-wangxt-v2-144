"""Execute experiments: run each configuration over every query, evaluate,
and persist both the normalised rankings and the metrics.
"""
from __future__ import annotations

from typing import Any

import psycopg

from . import repo
from .config import settings
from .data.corpus import INDEX
from .db import get_os_client
from .metrics.dedup import normalise
from .metrics.evaluator import evaluate_run
from .search import client as search_client


def run_one_config(
    queries: list[dict],
    config: dict[str, Any],
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Return (raw run hits for the evaluator, stored ranking rows)."""
    os_client = get_os_client()
    run_hits: dict[str, list[dict]] = {}
    stored: dict[str, list[dict]] = {}
    for q in queries:
        result = search_client.search(
            os_client, INDEX, q["text"], config, size=settings.max_fetch
        )
        raw_hits = result["hits"]
        run_hits[q["query_id"]] = raw_hits

        ranking = normalise(raw_hits)
        # scores/tie flags come from raw hits
        raw_by_doc = {h["doc_id"]: h for h in raw_hits}
        rows: list[dict] = []
        for rank, h in enumerate(ranking.kept, start=1):
            raw = raw_by_doc[h.doc_id]
            rows.append(
                {
                    "rank": rank,
                    "raw_rank": h.raw_rank,
                    "doc_id": h.doc_id,
                    "canonical_id": h.canonical_id,
                    "score": h.score,
                    "tied": raw.get("tied", False),
                    "duplicate": False,
                }
            )
        dup_rank = len(ranking.kept)
        for h in [x for x in ranking.hits if not x.kept]:
            dup_rank += 1
            raw = raw_by_doc[h.doc_id]
            rows.append(
                {
                    "rank": dup_rank,
                    "raw_rank": h.raw_rank,
                    "doc_id": h.doc_id,
                    "canonical_id": h.canonical_id,
                    "score": h.score,
                    "tied": raw.get("tied", False),
                    "duplicate": True,
                    "duplicate_of": h.duplicate_of,
                }
            )
        stored[q["query_id"]] = rows
    return run_hits, stored


def execute_experiment(conn: psycopg.Connection, exp: dict) -> dict:
    queries = repo.fetchall(conn, "SELECT query_id, text FROM queries ORDER BY query_id")
    qrels = repo.load_qrels(conn, exp["judgment_set_id"])

    os_client = get_os_client()
    snapshots = {
        "index": INDEX,
        "settings_snapshot": os_client.indices.get_settings(index=INDEX)[INDEX]["settings"],
        "mapping_snapshot": os_client.indices.get_mapping(index=INDEX)[INDEX]["mappings"],
    }

    repo.save_experiment(conn, exp, snapshots, replace=True)

    summary: dict[str, Any] = {"experiment_id": exp["experiment_id"], "runs": {}}

    def _run(role: str, config_id: str | None) -> None:
        if not config_id:
            return
        cfg = repo.load_run_config(conn, config_id)
        run_hits, stored = run_one_config(queries, cfg["config"])
        metrics = evaluate_run(qrels, run_hits)
        repo.save_run(
            conn, exp["experiment_id"], role, config_id, INDEX,
            cfg["config"], stored, metrics,
        )
        summary["runs"][role] = metrics

    _run("treatment", exp["treatment_config_id"])
    _run("baseline", exp["baseline_config_id"])
    return summary
