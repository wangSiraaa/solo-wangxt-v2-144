"""Tests for metric policy: denominators, cutoffs, unjudged docs, duplicates,
zero-relevant and missing queries. These pin exactly the semantics the UI shows.
"""
from __future__ import annotations

import math

from app.metrics.dedup import normalise
from app.metrics.evaluator import delta, evaluate_run


def _hit(doc_id, cid, score):
    return {"doc_id": doc_id, "canonical_id": cid, "score": score}


def test_duplicate_doc_counted_once_in_run():
    hits = [_hit("x-1", "C1", 9.0), _hit("x-2", "C1", 9.0)]
    n = normalise(hits)
    assert len(n.kept) == 1
    assert n.num_duplicates_dropped == 1
    assert not n.kept[0].duplicate_of
    assert n.hits[1].duplicate_of == "C1"


def test_duplicate_does_not_double_credit():
    # One relevant canonical doc appearing twice must give the same NDCG as once.
    qrels = {"q": {"C1": 3}}
    dup = {"q": [_hit("a", "C1", 9.0), _hit("b", "C1", 9.0)]}
    single = {"q": [_hit("a", "C1", 9.0)]}
    assert evaluate_run(qrels, dup)["aggregate"] == evaluate_run(qrels, single)["aggregate"]
    row = evaluate_run(qrels, dup)["per_query"][0]
    assert row["duplicates_dropped"] == 1
    assert row["num_returned"] == 1


def test_duplicate_keeps_highest_score_and_earliest_position():
    hits = [_hit("low", "C1", 1.0), _hit("high", "C1", 9.0)]
    n = normalise(hits)
    # deterministic sort puts high first; it is the kept representative
    assert n.kept[0].doc_id == "high"
    assert n.kept[0].score == 9.0


def test_zero_relevant_metrics_are_null_but_raw_retained():
    # judged, all grade 0
    qrels = {"q": {"C1": 0, "C2": 0}}
    run = {"q": [_hit("a", "C1", 5.0), _hit("b", "C2", 4.0)]}
    row = evaluate_run(qrels, run)["per_query"][0]
    assert row["ndcg_at_10"] is None
    assert row["mrr_at_10"] is None
    assert row["recall_at_100"] is None
    assert row["judged_at_10"] == 0.2  # 2 judged in top 10
    # raw trec_eval numeric value is kept for auditing
    assert row["ndcg_raw_zero_rel"] == 0.0


def test_missing_run_is_zero_not_dropped_from_mean():
    qrels = {"q1": {"A": 3}, "q2": {"B": 3}}
    run = {"q1": [_hit("a", "A", 9.0)]}  # q2 entirely missing
    out = evaluate_run(qrels, run)
    rows = {r["query_id"]: r for r in out["per_query"]}
    assert rows["q2"]["num_returned"] == 0
    assert rows["q2"]["ndcg_at_10"] == 0.0
    assert rows["q2"]["mrr_at_10"] == 0.0
    # mean over both queries, not just q1
    assert out["counts"]["num_missing_run_queries"] == 1
    assert math.isclose(out["aggregate"]["mrr_at_10"], 0.5)


def test_recall_denominator_is_judged_relevant_only():
    qrels = {"q": {"A": 3, "B": 2, "C": 1}}
    run = {"q": [_hit("a", "A", 9.0)]}  # finds 1 of 3 judged relevant
    row = evaluate_run(qrels, run)["per_query"][0]
    assert math.isclose(row["recall_at_100"], 1 / 3)


def test_unjudged_doc_counts_zero_gain_not_in_idcg():
    # judged relevant A in rank 2; unjudged X in rank 1
    qrels = {"q": {"A": 3}}
    run = {"q": [_hit("x", "X", 9.0), _hit("a", "A", 8.0)]}
    row = evaluate_run(qrels, run)["per_query"][0]
    # DCG = (2^3-1)/log2(3) ; IDCG = 7  => 1/log2(3)
    assert math.isclose(row["ndcg_at_10"], 1 / math.log2(3), rel_tol=1e-9)
    assert row["judged_at_10"] == 0.1  # only A judged in top 10


def test_mrr_uses_first_relevant_rank():
    qrels = {"q": {"A": 3}}
    run = {"q": [_hit("x", "X", 9.0), _hit("y", "Y", 8.0), _hit("a", "A", 7.0)]}
    row = evaluate_run(qrels, run)["per_query"][0]
    assert math.isclose(row["mrr_at_10"], 1 / 3)


def test_mrr_cutoff_excludes_relevant_beyond_10():
    qrels = {"q": {"A": 3}}
    # relevant doc at rank 11 -> MRR@10 must be 0
    run = {"q": [_hit(f"x{i}", f"X{i}", 100 - i) for i in range(10)]
           + [_hit("a", "A", 1.0)]}
    row = evaluate_run(qrels, run)["per_query"][0]
    assert row["mrr_at_10"] == 0.0


def test_grade_zero_is_not_relevant_for_binary_metrics():
    qrels = {"q": {"A": 0, "B": 1}}
    run = {"q": [_hit("a", "A", 9.0), _hit("b", "B", 8.0)]}
    row = evaluate_run(qrels, run)["per_query"][0]
    # first grade>=1 doc is B at rank 2
    assert math.isclose(row["mrr_at_10"], 0.5)


def test_delta_none_when_baseline_missing():
    assert math.isclose(delta(0.9, 0.8), 0.1)
    assert delta(0.9, None) is None
    assert delta(None, 0.8) is None


def test_aggregate_excludes_null_zero_rel_queries():
    qrels = {"good": {"A": 3}, "empty": {"Z": 0}}
    run = {"good": [_hit("a", "A", 9.0)], "empty": [_hit("z", "Z", 9.0)]}
    out = evaluate_run(qrels, run)
    # mean over the single defined query only
    assert math.isclose(out["aggregate"]["ndcg_at_10"], 1.0)
    assert out["counts"]["num_queries_evaluated"]["ndcg_at_10"] == 1
    assert out["counts"]["num_zero_relevant_queries"] == 1


def test_tie_order_is_deterministic_by_doc_id():
    hits = [_hit("z", "CZ", 5.0), _hit("a", "CA", 5.0), _hit("m", "CM", 5.0)]
    n1 = normalise([dict(h) for h in hits])
    n2 = normalise([dict(h) for h in reversed(hits)])
    assert [h.doc_id for h in n1.kept] == [h.doc_id for h in n2.kept] == ["a", "m", "z"]
