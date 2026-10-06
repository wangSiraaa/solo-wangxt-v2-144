from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import metrics, models, services
from ..db import get_db

router = APIRouter(tags=["experiments"])


class ExperimentCreate(BaseModel):
    name: str
    description: str = ""
    judgment_set_id: int
    index_name: str
    baseline_config: dict
    treatment_config: dict


def _run_summary(run: models.Run | None):
    if run is None:
        return None
    return {
        "id": run.id, "role": run.role, "status": run.status,
        "index_name": run.index_name, "query_config": run.query_config,
        "metrics": run.metrics, "error": run.error,
        "completed_at": run.completed_at,
    }


def _experiment_json(exp: models.Experiment):
    runs = {r.role: r for r in exp.runs}
    return {
        "id": exp.id, "name": exp.name, "description": exp.description,
        "judgment_set_id": exp.judgment_set_id,
        "judgment_set": f"{exp.judgment_set.name}@{exp.judgment_set.version}",
        "index_name": exp.index_name,
        "baseline_config": exp.baseline_config,
        "treatment_config": exp.treatment_config,
        "created_at": exp.created_at,
        "baseline": _run_summary(runs.get("baseline")),
        "treatment": _run_summary(runs.get("treatment")),
    }


@router.get("/experiments")
def list_experiments(db: Session = Depends(get_db)):
    exps = db.query(models.Experiment).order_by(models.Experiment.id).all()
    return [_experiment_json(e) for e in exps]


@router.post("/experiments", status_code=201)
def create_experiment(body: ExperimentCreate, db: Session = Depends(get_db)):
    if not db.get(models.JudgmentSet, body.judgment_set_id):
        raise HTTPException(404, "judgment set not found")
    exp = models.Experiment(**body.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return _experiment_json(exp)


@router.get("/experiments/{exp_id}")
def experiment_detail(exp_id: int, db: Session = Depends(get_db)):
    exp = db.get(models.Experiment, exp_id)
    if not exp:
        raise HTTPException(404, "experiment not found")
    return _experiment_json(exp)


@router.post("/experiments/{exp_id}/runs/{role}", status_code=201)
def run_experiment(exp_id: int, role: str, db: Session = Depends(get_db)):
    exp = db.get(models.Experiment, exp_id)
    if not exp:
        raise HTTPException(404, "experiment not found")
    if role not in ("baseline", "treatment"):
        raise HTTPException(400, "role must be 'baseline' or 'treatment'")
    run = services.execute_run(db, exp, role)
    if run.status != "completed":
        raise HTTPException(502, f"run failed: {run.error}")
    return _run_summary(run)


def _completed_runs(db: Session, exp_id: int):
    exp = db.get(models.Experiment, exp_id)
    if not exp:
        raise HTTPException(404, "experiment not found")
    runs = {r.role: r for r in exp.runs if r.status == "completed"}
    missing = [r for r in ("baseline", "treatment") if r not in runs]
    if missing:
        raise HTTPException(
            409,
            f"cannot compute lift: missing completed run(s) {missing}. "
            "Run both configurations before comparing; no estimate is "
            "shown without a real baseline.")
    return exp, runs["baseline"], runs["treatment"]


@router.get("/experiments/{exp_id}/compare")
def compare(exp_id: int, db: Session = Depends(get_db)):
    exp, base, treat = _completed_runs(db, exp_id)
    queries = {q.id: q.text for q in db.query(models.Query).all()}

    def metrics_of(run):
        return {qm.query_id: qm for qm in run.query_metrics}

    bm, tm = metrics_of(base), metrics_of(treat)
    rows = []
    for qid in sorted(bm.keys() & tm.keys()):
        b, t = bm[qid], tm[qid]
        rows.append({
            "query_id": qid, "text": queries.get(qid, ""),
            "num_rel": b.num_rel,
            "baseline": {"ndcg": b.ndcg, "mrr": b.mrr, "recall": b.recall},
            "treatment": {"ndcg": t.ndcg, "mrr": t.mrr, "recall": t.recall},
            "delta": {
                "ndcg": t.ndcg - b.ndcg,
                "mrr": t.mrr - b.mrr,
                "recall": (t.recall - b.recall
                           if t.recall is not None and b.recall is not None
                           else None),
            },
        })
    return {
        "experiment": _experiment_json(exp),
        "aggregate": {
            role: getattr(run, "metrics") for role, run in
            (("baseline", base), ("treatment", treat))
        } | {"delta": {
            k: (treat.metrics[k] - base.metrics[k]
                if treat.metrics[k] is not None and base.metrics[k] is not None
                else None)
            for k in ("ndcg", "mrr", "recall")
        }},
        "queries": rows,
        "policy": metrics.POLICY_DESCRIPTION,
    }


@router.get("/experiments/{exp_id}/queries/{query_id}")
def query_drilldown(exp_id: int, query_id: str, db: Session = Depends(get_db)):
    exp, base, treat = _completed_runs(db, exp_id)
    query = db.get(models.Query, query_id)
    if not query:
        raise HTTPException(404, "query not found")

    grades = {j.doc_id: j.grade for j in exp.judgment_set.judgments
              if j.query_id == query_id}

    def rows_for(run):
        rows = (db.query(models.RunResult)
                .filter_by(run_id=run.id, query_id=query_id)
                .order_by(models.RunResult.rank).all())
        return [{
            "rank": r.rank, "doc_id": r.doc_id, "score": r.score,
            "kept": r.kept, "drop_reason": r.drop_reason,
            "grade": grades.get(r.doc_id),  # None => unjudged => scored 0
        } for r in rows]

    def qm(run):
        row = (db.query(models.QueryMetricRow)
               .filter_by(run_id=run.id, query_id=query_id).first())
        return ({"ndcg": row.ndcg, "mrr": row.mrr, "recall": row.recall,
                 "num_rel": row.num_rel} if row else None)

    # Rank movement across the two scored (kept) rankings.
    kept_base = {r["doc_id"]: i + 1 for i, r in
                 enumerate(x for x in rows_for(base) if x["kept"])}
    kept_treat = {r["doc_id"]: i + 1 for i, r in
                  enumerate(x for x in rows_for(treat) if x["kept"])}
    movement = {}
    for doc_id in kept_base.keys() | kept_treat.keys():
        if doc_id not in kept_base:
            movement[doc_id] = "new"
        elif doc_id not in kept_treat:
            movement[doc_id] = "dropped"
        else:
            movement[doc_id] = kept_treat[doc_id] - kept_base[doc_id]

    return {
        "experiment_id": exp_id, "query_id": query_id, "text": query.text,
        "grades": grades,
        "baseline": {"run_id": base.id, "query_config": base.query_config,
                     "metrics": qm(base), "results": rows_for(base)},
        "treatment": {"run_id": treat.id, "query_config": treat.query_config,
                      "metrics": qm(treat), "results": rows_for(treat)},
        "movement": movement,
        "policy": metrics.POLICY_DESCRIPTION,
    }
