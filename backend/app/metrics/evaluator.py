"""Evaluation engine built on pytrec_eval (trec_eval 9.0 bindings).

Pipeline for one run:

  qrels (judgments, keyed by canonical_id)  ──┐
                                              ├─► pytrec_eval ─► per-query metrics
  raw run hits ─► normalise (sort+dedup)  ────┘

Missing-run queries are inserted as empty runs (score 0 for every metric) so a
retrieval failure cannot silently drop a query from the average. Queries whose
qrel set contains *no* relevant document are mathematically undefined for
NDCG/MRR/recall: we return ``None`` for those metrics and exclude them from the
mean, while keeping the raw trec_eval numeric value for auditing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytrec_eval

from .dedup import NormalisedRanking, normalise
from .policy import CUTOFFS, REL_THRESHOLD

# pytrec measure names, see https://github.com/cvangysel/pytrec_eval
_NDCG = f"ndcg_cut_{CUTOFFS['ndcg']}"
_RECALL = f"recall_{CUTOFFS['recall']}"
_MEASURES = {_NDCG, _RECALL, "recip_rank"}


@dataclass
class QueryEvaluation:
    query_id: str
    num_relevant: int                 # distinct grade >= threshold canonical docs
    num_returned: int                 # deduped hits returned
    num_in_cutoff: int                # deduped hits within the NDCG/MRR cutoff
    duplicates_dropped: int
    ndcg_at_10: float | None
    mrr_at_10: float | None
    recall_at_100: float | None
    judged_at_10: float
    ndcg_raw_zero_rel: float | None   # raw trec_eval value when undefined
    mrr_raw_zero_rel: float | None
    recall_raw_zero_rel: float | None

    def as_row(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "num_relevant": self.num_relevant,
            "num_returned": self.num_returned,
            "num_in_cutoff": self.num_in_cutoff,
            "duplicates_dropped": self.duplicates_dropped,
            "ndcg_at_10": self.ndcg_at_10,
            "mrr_at_10": self.mrr_at_10,
            "recall_at_100": self.recall_at_100,
            "judged_at_10": self.judged_at_10,
            "ndcg_raw_zero_rel": self.ndcg_raw_zero_rel,
            "mrr_raw_zero_rel": self.mrr_raw_zero_rel,
            "recall_raw_zero_rel": self.recall_raw_zero_rel,
        }


def _safe_mean(values: list[float | None]) -> float | None:
    defined = [v for v in values if v is not None]
    if not defined:
        return None
    return sum(defined) / len(defined)


def evaluate_run(
    qrels: dict[str, dict[str, int]],
    run_hits: dict[str, list[dict]],
) -> dict[str, Any]:
    """Evaluate one run against a qrel set.

    ``qrels`` maps query_id -> {canonical_doc_id: grade}.
    ``run_hits`` maps query_id -> raw ordered hits (dicts with doc_id,
    canonical_id, score).
    """
    # Normalise every query (sort ties deterministically + dedup copies).
    rankings: dict[str, NormalisedRanking] = {
        qid: normalise(hits) for qid, hits in run_hits.items()
    }

    # Full runs up to max fetch (used for recall@100 and ndcg@10; pytrec handles
    # the internal cutoff for ndcg).
    run_full: dict[str, dict[str, float]] = {}
    # Runs truncated to the MRR cutoff *before* recip_rank, which in trec_eval
    # has no cutoff parameter of its own.
    run_mrr: dict[str, dict[str, float]] = {}

    for qid, ranking in rankings.items():
        run_full[qid] = {h.canonical_id: h.score for h in ranking.kept}
        run_mrr[qid] = {
            h.canonical_id: h.score for h in ranking.kept[: CUTOFFS["mrr"]]
        }

    # Queries in qrels but absent from the run are retrieval failures: insert
    # explicit empty runs so they count as 0 instead of vanishing.
    for qid in qrels:
        run_full.setdefault(qid, {})
        run_mrr.setdefault(qid, {})
        rankings.setdefault(qid, normalise([]))

    scorer_full = pytrec_eval.RelevanceEvaluator(qrels, _MEASURES)
    scored_full = scorer_full.evaluate(run_full)
    scorer_mrr = pytrec_eval.RelevanceEvaluator(qrels, {"recip_rank"})
    scored_mrr = scorer_mrr.evaluate(run_mrr)

    judged_ids = {qid: set(docs) for qid, docs in qrels.items()}
    rel_ids: dict[str, set[str]] = {}
    for qid, docs in qrels.items():
        rel_ids[qid] = {d for d, g in docs.items() if g >= REL_THRESHOLD}

    rows: list[QueryEvaluation] = []
    for qid in qrels:
        ranking = rankings[qid]
        kept = ranking.kept
        rel_n = len(rel_ids[qid])
        top_cutoff = kept[: CUTOFFS["ndcg"]]
        judged_hits = sum(1 for h in top_cutoff if h.canonical_id in judged_ids[qid])
        judged_at_k = judged_hits / CUTOFFS["judged"]

        full = scored_full[qid]
        mrr_val = scored_mrr[qid]["recip_rank"]

        has_rel = rel_n > 0
        row = QueryEvaluation(
            query_id=qid,
            num_relevant=rel_n,
            num_returned=len(kept),
            num_in_cutoff=len(top_cutoff),
            duplicates_dropped=ranking.num_duplicates_dropped,
            ndcg_at_10=full[_NDCG] if has_rel else None,
            mrr_at_10=mrr_val if has_rel else None,
            recall_at_100=full[_RECALL] if has_rel else None,
            judged_at_10=judged_at_k,
            ndcg_raw_zero_rel=full[_NDCG] if not has_rel else None,
            mrr_raw_zero_rel=mrr_val if not has_rel else None,
            recall_raw_zero_rel=full[_RECALL] if not has_rel else None,
        )
        rows.append(row)

    metrics = {
        "ndcg_at_10": _safe_mean([r.ndcg_at_10 for r in rows]),
        "mrr_at_10": _safe_mean([r.mrr_at_10 for r in rows]),
        "recall_at_100": _safe_mean([r.recall_at_100 for r in rows]),
        "judged_at_10": sum(r.judged_at_10 for r in rows) / len(rows) if rows else None,
    }
    counts = {
        "num_queries": len(rows),
        "num_queries_evaluated": {
            "ndcg_at_10": sum(1 for r in rows if r.ndcg_at_10 is not None),
            "mrr_at_10": sum(1 for r in rows if r.mrr_at_10 is not None),
            "recall_at_100": sum(1 for r in rows if r.recall_at_100 is not None),
        },
        "num_zero_relevant_queries": sum(1 for r in rows if r.num_relevant == 0),
        "num_missing_run_queries": sum(1 for qid in qrels if not rankings[qid].kept),
        "num_duplicates_dropped": sum(r.duplicates_dropped for r in rows),
    }
    return {
        "aggregate": metrics,
        "counts": counts,
        "per_query": [r.as_row() for r in rows],
    }


def delta(treatment: float | None, baseline: float | None) -> float | None:
    """Absolute delta treatment − baseline. ``None`` if either side is missing.

    We never fabricate a baseline value: no baseline run means no delta rather
    than treating the missing run as zero improvement.
    """
    if treatment is None or baseline is None:
        return None
    return treatment - baseline
