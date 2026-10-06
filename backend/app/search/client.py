"""Local OpenSearch retrieval layer.

Design choices relevant to reproducibility:

* Every evaluation index is created with ``number_of_shards: 1`` so identical
  queries always hit the same shard.
* Every search request adds an explicit sort ``_score desc, _id asc``. OpenSearch
  does not define an order for equal scores, so tied BM25 scores would otherwise
  come back in an arbitrary (Lucene docID) order. The ``_id`` tie-break makes
  rankings — and therefore MRR/NDCG on tied documents — fully deterministic.
* ``run_configs`` only change query-side parameters (field boosts, operator);
  the index snapshot is identical, which is what makes baseline vs. treatment a
  controlled comparison.
"""
from __future__ import annotations

from typing import Any

from opensearchpy import OpenSearch

DEFAULT_RUN_CONFIG: dict[str, Any] = {
    "title_boost": 1.0,
    "body_boost": 1.0,
    "operator": "or",
    "analyzer": "standard",
}

INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "index.refresh_interval": "1s",
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "canonical_id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "standard"},
            "body": {"type": "text", "analyzer": "standard"},
            "tags": {"type": "keyword"},
            "content_hash": {"type": "keyword"},
        }
    },
}


def ensure_index(client: OpenSearch, index: str) -> None:
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body=INDEX_SETTINGS)


def index_corpus(client: OpenSearch, index: str, docs: list[dict]) -> dict:
    """Bulk-index ``docs`` (doc_id, canonical_id, title, body, ...). Deletes
    any prior index so seeding is idempotent."""
    if client.indices.exists(index=index):
        client.indices.delete(index=index)
    ensure_index(client, index)
    body: list[dict] = []
    for d in docs:
        body.append({"index": {"_index": index, "_id": d["doc_id"]}})
        body.append(
            {
                "doc_id": d["doc_id"],
                "canonical_id": d["canonical_id"],
                "title": d["title"],
                "body": d["body"],
                "tags": d.get("tags", []),
                "content_hash": d.get("content_hash", d["canonical_id"]),
            }
        )
    resp = client.bulk(body=body, refresh="true")
    return {
        "index": index,
        "indexed": len(docs),
        "errors": resp.get("errors"),
        "settings_snapshot": client.indices.get_settings(index=index)[index]["settings"],
        "mapping_snapshot": client.indices.get_mapping(index=index)[index]["mappings"],
    }


def _query_body(text: str, cfg: dict[str, Any], size: int) -> dict:
    title_boost = float(cfg.get("title_boost", 1.0))
    body_boost = float(cfg.get("body_boost", 1.0))
    return {
        "size": size,
        # Deterministic tie-break: equal scores ordered by doc_id ascending.
        "sort": [{"_score": {"order": "desc"}}, {"_id": {"order": "asc"}}],
        "query": {
            "bool": {
                "should": [
                    {
                        "match": {
                            "title": {
                                "query": text,
                                "analyzer": cfg.get("analyzer", "standard"),
                                "operator": cfg.get("operator", "or"),
                                "boost": title_boost,
                            }
                        }
                    },
                    {
                        "match": {
                            "body": {
                                "query": text,
                                "analyzer": cfg.get("analyzer", "standard"),
                                "operator": cfg.get("operator", "or"),
                                "boost": body_boost,
                            }
                        }
                    },
                ]
            }
        },
    }


def search(
    client: OpenSearch,
    index: str,
    text: str,
    run_config: dict[str, Any],
    size: int = 100,
) -> dict[str, Any]:
    resp = client.search(index=index, body=_query_body(text, run_config, size))
    hits = []
    for i, h in enumerate(resp["hits"]["hits"]):
        src = h.get("_source", {})
        hits.append(
            {
                "rank": i + 1,
                "doc_id": h["_id"],
                "canonical_id": src.get("canonical_id", h["_id"]),
                "title": src.get("title", ""),
                "body": src.get("body", ""),
                "tags": src.get("tags", []),
                "score": float(h.get("_score") or 0.0),
            }
        )
    # annotate tie groups (post-pass so group ids are stable)
    _annotate_ties(hits)
    return {
        "index": index,
        "query": text,
        "run_config": run_config,
        "total_hits": resp["hits"]["total"]["value"],
        "max_score_est": resp["hits"].get("max_score"),
        "hits": hits,
    }


def _annotate_ties(hits: list[dict]) -> None:
    """Mark every hit that shares a score with another hit."""
    counts: dict[float, int] = {}
    for h in hits:
        counts[h["score"]] = counts.get(h["score"], 0) + 1
    for h in hits:
        h["tied"] = counts[h["score"]] > 1
