"""Run execution: retrieve from OpenSearch, apply the metric policy,
persist the exact scored artifact. Shared by the API router and the seed
script so seeded runs and API-triggered runs are identical."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from . import metrics, models, retrieval


def execute_run(db: Session, experiment: models.Experiment, role: str,
                client=None) -> models.Run:
    if role not in ("baseline", "treatment"):
        raise ValueError("role must be 'baseline' or 'treatment'")
    config = (experiment.baseline_config if role == "baseline"
              else experiment.treatment_config)
    client = client or retrieval.get_client()

    # Replace any previous run for this role.
    old = (db.query(models.Run)
           .filter_by(experiment_id=experiment.id, role=role)
           .first())
    if old:
        db.delete(old)
        db.flush()

    run = models.Run(
        experiment_id=experiment.id,
        role=role,
        index_name=experiment.index_name,
        query_config=config,
        status="running",
    )
    db.add(run)
    db.flush()

    try:
        judgments = [
            (j.query_id, j.doc_id, j.grade)
            for j in experiment.judgment_set.judgments
        ]
        qrels = metrics.build_qrels(judgments)
        queries = {q.id: q.text for q in db.query(models.Query).all()}

        raw_run: dict[str, list[tuple[str, float]]] = {}
        for qid in qrels:
            raw_run[qid] = retrieval.search(
                client, experiment.index_name, queries[qid], config)

        # Persist raw rows, marking what the scoring pipeline drops.
        for qid, hits in raw_run.items():
            kept_ids: set[str] = set()
            for rank, (doc_id, score) in enumerate(hits, start=1):
                kept, reason = True, None
                if doc_id in kept_ids:
                    kept, reason = False, "duplicate"
                elif len(kept_ids) >= metrics.CUTOFF:
                    kept, reason = False, "cutoff"
                if kept:
                    kept_ids.add(doc_id)
                db.add(models.RunResult(
                    run_id=run.id, query_id=qid, rank=rank, doc_id=doc_id,
                    score=score, kept=kept, drop_reason=reason))

        agg = metrics.evaluate_run(qrels, raw_run)
        for qm in agg.per_query:
            db.add(models.QueryMetricRow(
                run_id=run.id, query_id=qm.query_id, ndcg=qm.ndcg,
                mrr=qm.mrr, recall=qm.recall, num_rel=qm.num_rel))

        duplicates_removed = sum(
            1 for hits in raw_run.values()
            for i, (doc_id, _) in enumerate(hits)
            if doc_id in {d for d, _ in hits[:i]}
        )
        run.metrics = {
            "ndcg": round(agg.ndcg, 6),
            "mrr": round(agg.mrr, 6),
            "recall": (round(agg.recall, 6) if agg.recall is not None else None),
            "num_queries": agg.num_queries,
            "recall_query_count": agg.recall_query_count,
            "duplicates_removed": duplicates_removed,
            "policy": metrics.POLICY_DESCRIPTION,
        }
        run.status = "completed"
        run.completed_at = datetime.utcnow()
    except Exception as exc:  # pragma: no cover - surfaced via API
        run.status = "failed"
        run.error = str(exc)
    db.commit()
    db.refresh(run)
    return run
