"""OpenSearch retrieval. Query configs are plain JSON so a run is fully
described by (index_name, query_config) and can be reproduced later."""
from __future__ import annotations

from opensearchpy import OpenSearch

from .config import OPENSEARCH_URL
from .metrics import RETRIEVAL_DEPTH

INDEX_MAPPINGS = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "title": {"type": "text"},
            "text": {"type": "text"},
        }
    },
}


def get_client() -> OpenSearch:
    return OpenSearch(OPENSEARCH_URL, timeout=30)


def build_query(query_text: str, config: dict) -> dict:
    """Translate a stored query config into an OpenSearch query clause."""
    qtype = config.get("type", "match")
    if qtype == "match":
        return {"match": {config["field"]: query_text}}
    if qtype == "multi_match":
        clause: dict = {
            "query": query_text,
            "fields": config["fields"],
            "type": config.get("match_type", "best_fields"),
        }
        if "tie_breaker" in config:
            clause["tie_breaker"] = config["tie_breaker"]
        return {"multi_match": clause}
    if qtype == "match_phrase":
        return {"match_phrase": {config["field"]: query_text}}
    raise ValueError(f"unknown query config type: {qtype!r}")


def search(
    client: OpenSearch, index: str, query_text: str, config: dict
) -> list[tuple[str, float]]:
    """Return ranked [(doc_id, score)] at RETRIEVAL_DEPTH.

    The list may contain the same logical doc_id twice when the document
    was indexed more than once (re-ingestion duplicates); deduplication
    is the scoring pipeline's job (metrics.dedupe_run).
    """
    resp = client.search(
        index=index,
        body={
            "size": RETRIEVAL_DEPTH,
            "query": build_query(query_text, config),
            "_source": ["doc_id"],
        },
    )
    return [(hit["_source"]["doc_id"], hit["_score"]) for hit in resp["hits"]["hits"]]


def ensure_index(client: OpenSearch, index: str) -> None:
    if client.indices.exists(index=index):
        client.indices.delete(index=index)
    client.indices.create(index=index, body=INDEX_MAPPINGS)


def index_docs(client: OpenSearch, index: str, docs: list[dict]) -> None:
    """docs: [{"_id": ..., "doc_id": ..., "title": ..., "text": ...}]"""
    for doc in docs:
        client.index(index=index, id=doc["_id"], body={
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "text": doc["text"],
        })
    client.indices.refresh(index=index)
