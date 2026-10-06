"""FastAPI application: experiments, qrels, ranking comparison, metric policy.

The Vue 3 frontend talks to these endpoints. Static built assets are served in
production (see /static mount at the bottom).
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import repo
from .config import settings
from .db import get_db, get_os_client
from .metrics.delta import comparison_table, experiment_summary
from .metrics.evaluator import delta
from .metrics.policy import policy_payload
from .search import client as search_client

app = FastAPI(title="IR 排序评测", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    os_ok = get_os_client().ping()
    return {"status": "ok", "opensearch": os_ok}


@app.get("/api/policy")
def policy() -> dict:
    return policy_payload()


@app.get("/api/judgment-sets")
def list_judgment_sets(conn=Depends(get_db)) -> list[dict]:
    return repo.fetchall(conn, "SELECT * FROM judgment_sets ORDER BY created_at")


@app.get("/api/judges")
def list_judges(conn=Depends(get_db)) -> list[dict]:
    return repo.fetchall(conn, "SELECT * FROM judges ORDER BY judge_id")


@app.get("/api/queries")
def list_queries(set_id: str = "js-synth-v1", conn=Depends(get_db)) -> list[dict]:
    queries = repo.fetchall(conn, "SELECT * FROM queries ORDER BY query_id")
    qrels = repo.fetchall(
        conn,
        """
        SELECT qr.query_id, qr.canonical_doc_id, qr.grade, qr.judge_id,
               j.name AS judge_name, d.title, d.body, d.doc_id
        FROM qrels qr
        JOIN judges j ON j.judge_id = qr.judge_id
        LEFT JOIN (
            SELECT DISTINCT ON (canonical_id) canonical_id, title, body, doc_id
            FROM corpus_docs ORDER BY canonical_id, doc_id
        ) d ON d.canonical_id = qr.canonical_doc_id
        WHERE qr.set_id = %s
        ORDER BY qr.query_id, qr.grade DESC
        """,
        (set_id,),
    )
    grouped: dict[str, list[dict]] = {}
    for r in qrels:
        grouped.setdefault(r["query_id"], []).append(r)
    for q in queries:
        q["qrels"] = grouped.get(q["query_id"], [])
    return queries


@app.get("/api/experiments")
def list_experiments(conn=Depends(get_db)) -> list[dict]:
    exps = repo.fetchall(conn, "SELECT * FROM experiments ORDER BY created_at")
    for e in exps:
        agg = repo.fetchall(
            conn,
            """
            SELECT role, ndcg_at_10, mrr_at_10, recall_at_100, judged_at_10
            FROM run_metrics_aggregate WHERE experiment_id=%s
            """,
            (e["experiment_id"],),
        )
        e["aggregate"] = {a["role"]: a for a in agg}
    return exps


@app.get("/api/experiments/{experiment_id}/summary")
def get_summary(experiment_id: str, conn=Depends(get_db)) -> dict:
    exp = repo.fetchone(
        conn, "SELECT * FROM experiments WHERE experiment_id=%s", (experiment_id,)
    )
    if not exp:
        raise HTTPException(404, "experiment not found")
    return experiment_summary(conn, experiment_id)


@app.get("/api/experiments/{experiment_id}/queries/{query_id}")
def get_query_detail(experiment_id: str, query_id: str, conn=Depends(get_db)) -> dict:
    """Per-query drilldown: metrics with delta and side-by-side rankings."""
    exp = repo.fetchone(
        conn, "SELECT * FROM experiments WHERE experiment_id=%s", (experiment_id,)
    )
    if not exp:
        raise HTTPException(404, "experiment not found")
    query = repo.fetchone(
        conn, "SELECT * FROM queries WHERE query_id=%s", (query_id,)
    )
    if not query:
        raise HTTPException(404, "query not found")

    roles = [r["role"] for r in repo.fetchall(
        conn, "SELECT role FROM runs WHERE experiment_id=%s", (experiment_id,)
    )]
    has_baseline = "baseline" in roles

    qrels = repo.fetchall(
        conn,
        """
        SELECT canonical_doc_id, grade, judge_id FROM qrels
        WHERE set_id=%s AND query_id=%s
        """,
        (exp["judgment_set_id"], query_id),
    )
    qrel_map = {r["canonical_doc_id"]: r for r in qrels}

    rankings: dict[str, list[dict]] = {}
    metrics_rows: dict[str, dict] = {}
    for role in roles:
        rankings[role] = repo.fetchall(
            conn,
            """
            SELECT rank, raw_rank, doc_id, canonical_doc_id, score, tied, duplicate
            FROM run_rankings
            WHERE experiment_id=%s AND role=%s AND query_id=%s
            ORDER BY rank
            """,
            (experiment_id, role, query_id),
        )
        m = repo.fetchone(
            conn,
            """
            SELECT * FROM run_metrics
            WHERE experiment_id=%s AND role=%s AND query_id=%s
            """,
            (experiment_id, role, query_id),
        )
        if m:
            metrics_rows[role] = m
        for h in rankings[role]:
            rel = qrel_map.get(h["canonical_doc_id"])
            h["grade"] = rel["grade"] if rel else None
            h["judged"] = rel is not None
            h["judge_id"] = rel["judge_id"] if rel else None

    metric_deltas = None
    if has_baseline:
        b, t = metrics_rows.get("baseline"), metrics_rows.get("treatment")
        metric_deltas = {}
        for key in ("ndcg_at_10", "mrr_at_10", "recall_at_100", "judged_at_10"):
            metric_deltas[key] = delta(t[key] if t else None, b[key] if b else None)

    return {
        "experiment": {
            "experiment_id": exp["experiment_id"],
            "name": exp["name"],
            "index_name": exp["index_name"],
            "judgment_set_id": exp["judgment_set_id"],
            "has_baseline": has_baseline,
        },
        "query": query,
        "qrels": qrels,
        "rankings": rankings,
        "metrics": metrics_rows,
        "metric_deltas": metric_deltas,
        "baseline_missing": not has_baseline,
    }


@app.get("/api/experiments/{experiment_id}/comparison")
def get_comparison(experiment_id: str, conn=Depends(get_db)) -> dict:
    """Aggregate + full per-query comparison table for the drilldown view."""
    return comparison_table(conn, experiment_id)


class SearchRequest(BaseModel):
    query: str
    config_id: str | None = None
    title_boost: float | None = None
    body_boost: float | None = None
    operator: str | None = None
    index: str | None = None
    size: int = 20


@app.post("/api/search")
def adhoc_search(req: SearchRequest, conn=Depends(get_db)) -> dict:
    """Re-run a query live with an arbitrary config (playground)."""
    cfg: dict[str, Any] = {}
    if req.config_id:
        row = repo.load_run_config(conn, req.config_id)
        if not row:
            raise HTTPException(404, "run config not found")
        cfg = dict(row["config"])
    for field in ("title_boost", "body_boost", "operator"):
        val = getattr(req, field)
        if val is not None:
            cfg[field] = val
    cfg.setdefault("title_boost", 1.0)
    cfg.setdefault("body_boost", 1.0)
    cfg.setdefault("operator", "or")
    cfg.setdefault("analyzer", "standard")
    from .data.corpus import INDEX
    index = req.index or INDEX
    return search_client.search(get_os_client(), index, req.query, cfg, size=req.size)


@app.get("/api/run-configs")
def run_configs(conn=Depends(get_db)) -> list[dict]:
    rows = repo.fetchall(conn, "SELECT * FROM run_configs ORDER BY config_id")
    return rows


# Serve the built frontend (single-port option). In dev, run Vite separately on
# :5173; it proxies /api here. Only mounted when a build output exists.
import os as _os

from fastapi.staticfiles import StaticFiles

_DIST = _os.getenv("IREVAL_FRONTEND_DIST", "../frontend/dist")
if _os.path.isdir(_DIST):
    app.mount(
        "/",
        StaticFiles(directory=_DIST, html=True),
        name="frontend",
    )
