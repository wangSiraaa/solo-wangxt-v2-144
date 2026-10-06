"""Metric computation with an explicit, documented evaluation policy.

Policy (also exposed via GET /api/metric-policy and README):

* Cutoff: every metric is computed at rank cutoff 10. Runs are truncated
  to the top 10 documents *before* scoring, so ``recip_rank`` is MRR@10.
* NDCG@10: trec_eval ``ndcg_cut.10`` with linear gains (gain = grade).
  The denominator (IDCG) is the ideal DCG over all judged documents for
  the query, including documents the run never retrieved.
* MRR@10: trec_eval ``recip_rank`` on the truncated run. Relevance is
  binary: grade >= 1 counts as relevant.
* Recall@10: trec_eval ``recall.10``. The denominator is the number of
  judged-relevant (grade >= 1) documents for the query. Queries with
  zero relevant documents have an undefined recall and are EXCLUDED from
  the recall average (``recall_query_count`` reports how many queries
  contributed). They still count toward NDCG/MRR averages as 0.0.
* Unjudged documents are treated as non-relevant (grade 0). This is the
  standard trec_eval pooling assumption.
* Duplicate documents: a run is deduplicated by logical ``doc_id``
  before scoring, keeping the best (lowest) rank. A duplicated document
  can therefore never earn credit twice.
* Ties: documents with identical scores are ordered by doc_id in
  descending lexicographic order (trec_eval convention).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytrec_eval

CUTOFF = 10
RETRIEVAL_DEPTH = 20  # how many hits OpenSearch returns; scoring truncates to CUTOFF

MEASURES = {"ndcg_cut.10", "recall.10", "recip_rank"}

POLICY_DESCRIPTION = {
    "cutoff": CUTOFF,
    "retrieval_depth": RETRIEVAL_DEPTH,
    "ndcg": "ndcg_cut.10, linear gains (gain=grade); IDCG over all judged docs",
    "mrr": "recip_rank on run truncated to 10 (MRR@10); grade>=1 is relevant",
    "recall": "recall.10; denominator = #judged-relevant (grade>=1); "
              "queries with 0 relevant docs are excluded from the average",
    "unjudged": "unjudged documents are treated as non-relevant (grade 0)",
    "duplicates": "runs are deduplicated by doc_id keeping the best rank; "
                  "a document can never be credited twice",
    "ties": "equal scores are broken by doc_id descending (trec_eval convention)",
}


@dataclass
class QueryMetric:
    query_id: str
    ndcg: float
    mrr: float
    recall: float | None  # None when the query has zero relevant docs
    num_rel: int


@dataclass
class AggregateMetric:
    ndcg: float
    mrr: float
    recall: float | None
    num_queries: int
    recall_query_count: int
    per_query: list[QueryMetric] = field(default_factory=list)


def dedupe_run(run: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Remove duplicate doc_ids, keeping the first (best-ranked) occurrence.

    ``run`` is a list of (doc_id, score) in retrieval rank order.
    """
    seen: set[str] = set()
    out: list[tuple[str, float]] = []
    for doc_id, score in run:
        if doc_id in seen:
            continue
        seen.add(doc_id)
        out.append((doc_id, score))
    return out


def truncate_run(run: list[tuple[str, float]], cutoff: int = CUTOFF) -> list[tuple[str, float]]:
    return run[:cutoff]


def build_qrels(judgments: list[tuple[str, str, int]]) -> dict[str, dict[str, int]]:
    """judgments: iterable of (query_id, doc_id, grade)."""
    qrels: dict[str, dict[str, int]] = {}
    for query_id, doc_id, grade in judgments:
        qrels.setdefault(query_id, {})[doc_id] = int(grade)
    return qrels


def evaluate_run(
    qrels: dict[str, dict[str, int]],
    run: dict[str, list[tuple[str, float]]],
) -> AggregateMetric:
    """Score one run against qrels under the module policy.

    ``run`` maps query_id -> ranked [(doc_id, score)]. Every judged query
    is evaluated; queries absent from ``run`` score as empty runs.
    """
    # Dedupe + truncate, then convert to the {qid: {docid: score}} shape.
    prepared: dict[str, dict[str, float]] = {}
    for qid in qrels:
        docs = truncate_run(dedupe_run(run.get(qid, [])))
        prepared[qid] = {doc_id: float(score) for doc_id, score in docs}

    evaluator = pytrec_eval.RelevanceEvaluator(qrels, MEASURES)
    raw = evaluator.evaluate(prepared)

    per_query: list[QueryMetric] = []
    for qid, qrel in qrels.items():
        num_rel = sum(1 for g in qrel.values() if g >= 1)
        scores = raw.get(qid, {})
        per_query.append(
            QueryMetric(
                query_id=qid,
                ndcg=scores.get("ndcg_cut_10", 0.0),
                mrr=scores.get("recip_rank", 0.0),
                recall=scores.get("recall_10", 0.0) if num_rel > 0 else None,
                num_rel=num_rel,
            )
        )

    n = len(per_query)
    recall_queries = [q for q in per_query if q.recall is not None]
    return AggregateMetric(
        ndcg=sum(q.ndcg for q in per_query) / n if n else 0.0,
        mrr=sum(q.mrr for q in per_query) / n if n else 0.0,
        recall=(sum(q.recall for q in recall_queries) / len(recall_queries))
        if recall_queries
        else None,
        num_queries=n,
        recall_query_count=len(recall_queries),
        per_query=per_query,
    )
