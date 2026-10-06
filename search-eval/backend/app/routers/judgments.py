from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(tags=["judgments"])


@router.get("/queries")
def list_queries(db: Session = Depends(get_db)):
    queries = db.query(models.Query).order_by(models.Query.id).all()
    judged = {}
    for (qid,) in db.query(models.Judgment.query_id).distinct():
        judged[qid] = True
    return [{"id": q.id, "text": q.text, "judged": q.id in judged}
            for q in queries]


@router.get("/judgment-sets")
def list_judgment_sets(db: Session = Depends(get_db)):
    sets = db.query(models.JudgmentSet).order_by(models.JudgmentSet.id).all()
    return [{
        "id": s.id, "name": s.name, "version": s.version,
        "description": s.description, "created_at": s.created_at,
        "num_judgments": len(s.judgments),
        "judges": sorted({j.judge.name for j in s.judgments}),
    } for s in sets]


@router.get("/judgment-sets/{set_id}")
def judgment_set_detail(set_id: int, db: Session = Depends(get_db)):
    jset = db.get(models.JudgmentSet, set_id)
    if not jset:
        raise HTTPException(404, "judgment set not found")
    queries = {q.id: q.text for q in db.query(models.Query).all()}
    by_query: dict[str, list] = {}
    for j in jset.judgments:
        by_query.setdefault(j.query_id, []).append({
            "doc_id": j.doc_id, "grade": j.grade, "judge": j.judge.name,
        })
    return {
        "id": jset.id, "name": jset.name, "version": jset.version,
        "description": jset.description,
        "queries": [{
            "query_id": qid, "text": queries.get(qid, ""),
            "judgments": sorted(items, key=lambda x: -x["grade"]),
            "num_rel": sum(1 for i in items if i["grade"] >= 1),
        } for qid, items in sorted(by_query.items())],
    }
