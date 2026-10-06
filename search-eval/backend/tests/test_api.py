import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

import pytest
from fastapi.testclient import TestClient

from app import models, retrieval
from app.db import Base, engine, get_db
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield TestClient(app)


def seed_data(monkeypatch, hits=None):
    """Insert one judgment set + experiment; stub OpenSearch retrieval."""
    hits = hits or {}
    monkeypatch.setattr(
        retrieval, "search",
        lambda client, index, text, config: hits.get(text, []))
    monkeypatch.setattr(retrieval, "get_client", lambda: None)

    db = next(get_db())
    judge = models.Judge(name="alice")
    db.add(judge)
    db.flush()
    q1 = models.Query(id="q1", text="alpha query")
    q2 = models.Query(id="q2", text="beta query")
    db.add_all([q1, q2])
    jset = models.JudgmentSet(name="js", version="v1")
    db.add(jset)
    db.flush()
    db.add_all([
        models.Judgment(judgment_set_id=jset.id, query_id="q1",
                        doc_id="a", grade=2, judge_id=judge.id),
        models.Judgment(judgment_set_id=jset.id, query_id="q1",
                        doc_id="b", grade=1, judge_id=judge.id),
        models.Judgment(judgment_set_id=jset.id, query_id="q2",
                        doc_id="c", grade=0, judge_id=judge.id),
    ])
    exp = models.Experiment(
        name="exp", judgment_set_id=jset.id, index_name="docs",
        baseline_config={"type": "match", "field": "text"},
        treatment_config={"type": "multi_match", "fields": ["title^3", "text"]})
    db.add(exp)
    db.commit()
    return exp.id


def test_compare_requires_both_runs(client, monkeypatch):
    exp_id = seed_data(monkeypatch)
    resp = client.get(f"/api/experiments/{exp_id}/compare")
    assert resp.status_code == 409
    assert "baseline" in resp.json()["detail"]

    client.post(f"/api/experiments/{exp_id}/runs/baseline")
    resp = client.get(f"/api/experiments/{exp_id}/compare")
    assert resp.status_code == 409  # still missing treatment


def test_run_and_compare_end_to_end(client, monkeypatch):
    hits = {
        "alpha query": [("a", 9.0), ("a", 8.5), ("b", 7.0), ("zz", 6.0)],
        "beta query": [("c", 5.0)],
    }
    exp_id = seed_data(monkeypatch, hits)

    for role in ("baseline", "treatment"):
        resp = client.post(f"/api/experiments/{exp_id}/runs/{role}")
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "completed"

    resp = client.get(f"/api/experiments/{exp_id}/compare")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["aggregate"]) == {"baseline", "treatment", "delta"}
    assert body["aggregate"]["baseline"]["duplicates_removed"] == 1
    assert body["aggregate"]["baseline"]["recall_query_count"] == 1  # q2 has 0 rel
    rows = {r["query_id"]: r for r in body["queries"]}
    assert rows["q1"]["baseline"]["recall"] == 1.0
    assert rows["q2"]["baseline"]["recall"] is None  # zero-relevant query

    detail = client.get(f"/api/experiments/{exp_id}").json()
    assert detail["baseline"]["query_config"] == {"type": "match", "field": "text"}
    assert detail["baseline"]["index_name"] == "docs"


def test_drilldown_marks_duplicates_and_movement(client, monkeypatch):
    hits = {"alpha query": [("a", 9.0), ("a", 8.5), ("b", 7.0)], "beta query": []}
    exp_id = seed_data(monkeypatch, hits)
    client.post(f"/api/experiments/{exp_id}/runs/baseline")
    client.post(f"/api/experiments/{exp_id}/runs/treatment")

    resp = client.get(f"/api/experiments/{exp_id}/queries/q1")
    assert resp.status_code == 200
    body = resp.json()
    results = body["baseline"]["results"]
    dup = next(r for r in results if r["drop_reason"] == "duplicate")
    assert dup["kept"] is False and dup["rank"] == 2
    assert body["grades"] == {"a": 2, "b": 1}
    assert body["movement"]["a"] == 0  # same scored rank in both runs


def test_create_experiment_validates_judgment_set(client):
    resp = client.post("/api/experiments", json={
        "name": "x", "judgment_set_id": 999, "index_name": "docs",
        "baseline_config": {}, "treatment_config": {}})
    assert resp.status_code == 404
