"""Ranking normalisation: deterministic tie-breaking and duplicate removal.

A single canonical document (same content hash) may surface multiple times.
trec_eval itself forbids repeated docs per query in a run — repeated docs make
its counts ill-defined. We normalise *before* scoring:

  1. stable-sort by (-score, doc_id) so tied scores have a defined order;
  2. collapse duplicate canonical_id values, keeping the highest score and the
     earliest raw position, and recording every dropped duplicate.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RankedHit:
    doc_id: str               # raw OpenSearch _id
    canonical_id: str         # content-hash identity used for judging
    score: float
    raw_rank: int | None = None  # 1-based rank as returned by OpenSearch
    duplicate_of: str | None = None  # canonical_id it duplicates, if dropped

    @property
    def kept(self) -> bool:
        return self.duplicate_of is None


@dataclass
class NormalisedRanking:
    hits: list[RankedHit]          # all hits, kept first then dropped duplicates
    kept: list[RankedHit]          # deduped hits used for scoring
    duplicate_groups: dict[str, int] = field(default_factory=dict)

    @property
    def num_duplicates_dropped(self) -> int:
        return sum(n - 1 for n in self.duplicate_groups.values())


def normalise(hits: list[dict]) -> NormalisedRanking:
    """Normalise raw search hits.

    Each hit dict needs: doc_id, canonical_id, score.
    """
    indexed = [
        RankedHit(
            doc_id=h["doc_id"],
            canonical_id=h["canonical_id"],
            score=float(h.get("score") or 0.0),
            raw_rank=i + 1,
        )
        for i, h in enumerate(hits)
    ]
    # Deterministic order regardless of how the engine ordered equal scores.
    indexed.sort(key=lambda h: (-h.score, h.doc_id))

    kept: list[RankedHit] = []
    dropped: list[RankedHit] = []
    groups: dict[str, int] = {}
    seen: set[str] = set()
    for h in indexed:
        groups[h.canonical_id] = groups.get(h.canonical_id, 0) + 1
        if h.canonical_id in seen:
            # A repeated copy of an already-kept canonical document: it stays
            # visible for comparison but is never sent to trec_eval.
            h.duplicate_of = h.canonical_id
            dropped.append(h)
        else:
            seen.add(h.canonical_id)
            kept.append(h)

    duplicate_groups = {cid: n for cid, n in groups.items() if n > 1}
    return NormalisedRanking(hits=kept + dropped, kept=kept, duplicate_groups=duplicate_groups)
