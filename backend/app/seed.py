"""Idempotent bootstrap: schema + reference data + OpenSearch index + runs.

Usage:  python -m app.seed
"""
from __future__ import annotations

import json
import pathlib

import psycopg

from . import repo
from .config import settings
from .data import corpus
from .db import get_os_client
from .search import client as search_client
from .services import execute_experiment

SCHEMA_SQL = pathlib.Path(__file__).with_name("schema.sql").read_text()


def reset_database(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL)
    conn.execute(
        "TRUNCATE run_metrics_aggregate, run_metrics, run_rankings, runs, "
        "experiments, qrels, corpus_docs, queries, run_configs, judgment_sets, "
        "judges RESTART IDENTITY CASCADE"
    )
    with conn.cursor() as cur:
        for j in corpus.JUDGES:
            cur.execute(
                "INSERT INTO judges(judge_id,name,team) VALUES(%s,%s,%s) "
                "ON CONFLICT (judge_id) DO NOTHING",
                (j["judge_id"], j["name"], j["team"]),
            )
        js = corpus.JUDGMENT_SET
        cur.execute(
            "INSERT INTO judgment_sets(set_id,name,description,version) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT (set_id) DO NOTHING",
            (js["set_id"], js["name"], js["description"], js["version"]),
        )
        for q in corpus.QUERIES:
            cur.execute(
                "INSERT INTO queries(query_id,text,title,scenario,note) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT (query_id) DO NOTHING",
                (q["query_id"], q["text"], q["title"], q["scenario"], q["note"]),
            )
        for d in corpus.DOCUMENTS:
            cur.execute(
                "INSERT INTO corpus_docs(doc_id,canonical_id,title,body,tags) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT (doc_id) DO NOTHING",
                (d["doc_id"], d["canonical_id"], d["title"], d["body"], d.get("tags", [])),
            )
        for r in corpus.QRELS:
            cur.execute(
                """
                INSERT INTO qrels(set_id,query_id,canonical_doc_id,grade,judge_id)
                VALUES(%s,%s,%s,%s,%s)
                ON CONFLICT (set_id,query_id,canonical_doc_id) DO NOTHING
                """,
                (r["set_id"] if "set_id" in r else js["set_id"],
                 r["query_id"], r["doc_id"], r["grade"], r["judge_id"]),
            )
        for rc in corpus.RUN_CONFIGS:
            cur.execute(
                "INSERT INTO run_configs(config_id,name,description,config) "
                "VALUES(%s,%s,%s,%s::jsonb) ON CONFLICT (config_id) DO NOTHING",
                (rc["config_id"], rc["name"], rc["description"],
                 json.dumps(rc["config"])),
            )
    conn.commit()


def seed_index() -> dict:
    os_client = get_os_client()
    return search_client.index_corpus(os_client, corpus.INDEX, corpus.DOCUMENTS)


def main() -> None:
    with psycopg.connect(settings.database_url) as conn:
        reset_database(conn)
    idx = seed_index()
    print(f"indexed {idx['indexed']} docs into {idx['index']} (errors={idx['errors']})")
    with psycopg.connect(settings.database_url) as conn:
        for exp in corpus.EXPERIMENTS:
            summary = execute_experiment(conn, exp)
            print(f"experiment {summary['experiment_id']}: roles={list(summary['runs'])}")
        conn.commit()
    print("seed complete")


if __name__ == "__main__":
    main()
