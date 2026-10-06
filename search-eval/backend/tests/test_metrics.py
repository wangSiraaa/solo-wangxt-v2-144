"""Tests for the explicit metric policy in app.metrics."""
import math

from app.metrics import build_qrels, dedupe_run, evaluate_run, truncate_run


def test_dedupe_keeps_best_rank_only():
    run = [("a", 10.0), ("b", 8.0), ("a", 7.5), ("c", 5.0), ("b", 4.0)]
    assert dedupe_run(run) == [("a", 10.0), ("b", 8.0), ("c", 5.0)]


def test_duplicate_doc_never_scores_twice():
    # 'a' appears twice; without dedupe its gain would be counted twice.
    qrels = build_qrels([("q1", "a", 1), ("q1", "b", 1)])
    dup = evaluate_run(qrels, {"q1": [("a", 10.0), ("a", 9.0), ("b", 1.0)]})
    clean = evaluate_run(qrels, {"q1": [("a", 10.0), ("b", 1.0)]})
    assert dup.per_query[0].ndcg == clean.per_query[0].ndcg
    assert dup.recall == 1.0  # both relevant docs found, 'a' counted once


def test_zero_relevant_query_excluded_from_recall_only():
    qrels = build_qrels([
        ("q_zero", "x", 0), ("q_zero", "y", 0),      # zero-relevant query
        ("q_ok", "a", 2), ("q_ok", "b", 1),
    ])
    run = {
        "q_zero": [("x", 5.0), ("y", 4.0)],
        "q_ok": [("a", 5.0), ("b", 4.0)],
    }
    agg = evaluate_run(qrels, run)
    zero = next(q for q in agg.per_query if q.query_id == "q_zero")
    ok = next(q for q in agg.per_query if q.query_id == "q_ok")
    assert zero.recall is None and zero.num_rel == 0
    assert zero.ndcg == 0.0 and zero.mrr == 0.0
    assert agg.recall_query_count == 1          # only q_ok contributes
    assert agg.recall == ok.recall == 1.0
    assert agg.num_queries == 2                 # q_zero still in ndcg/mrr means


def test_unjudged_doc_treated_as_nonrelevant():
    qrels = build_qrels([("q1", "a", 3)])
    with_unjudged = evaluate_run(qrels, {"q1": [("zzz_unjudged", 9.0), ("a", 8.0)]})
    # The unjudged doc occupies rank 1 with zero gain; 'a' scores at rank 2.
    expected_dcg = 3.0 / math.log2(3)  # gain=grade at rank 2
    assert with_unjudged.per_query[0].ndcg == expected_dcg / 3.0
    assert with_unjudged.per_query[0].recall == 1.0  # recall unaffected


def test_cutoff_at_10():
    qrels = build_qrels([("q1", "target", 2)])
    run_at_10 = [(f"d{i}", 10.0 - i * 0.1) for i in range(9)] + [("target", 0.5)]
    run_at_11 = [(f"d{i}", 10.0 - i * 0.1) for i in range(10)] + [("target", 0.5)]
    assert evaluate_run(qrels, {"q1": run_at_10}).per_query[0].recall == 1.0
    beyond = evaluate_run(qrels, {"q1": run_at_11}).per_query[0]
    assert beyond.recall == 0.0 and beyond.mrr == 0.0


def test_mrr_is_reciprocal_rank_of_first_relevant():
    qrels = build_qrels([("q1", "a", 1), ("q1", "b", 1)])
    run = [("u1", 9.0), ("u2", 8.0), ("b", 7.0), ("a", 6.0)]
    assert evaluate_run(qrels, {"q1": run}).per_query[0].mrr == 1 / 3


def test_tied_scores_are_order_independent():
    qrels = build_qrels([("q1", "a", 2), ("q1", "b", 1)])
    run1 = evaluate_run(qrels, {"q1": [("a", 5.0), ("b", 5.0)]})
    run2 = evaluate_run(qrels, {"q1": [("b", 5.0), ("a", 5.0)]})
    assert run1.per_query[0].ndcg == run2.per_query[0].ndcg


def test_truncate_run():
    run = [(f"d{i}", float(i)) for i in range(20)]
    assert len(truncate_run(run)) == 10
