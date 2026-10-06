"""Synthetic evaluation corpus (local, fully reproducible — no external data).

Three deliberately adversarial scenarios are embedded:

* ``q_net_debug`` — two *different* canonical documents get identical BM25
  scores (their bodies have the same word multiset), exercising the score-tie
  policy. Their grades differ so the deterministic doc_id tie-break is visible.
* ``q_py_sort`` — the same canonical document (``C_PY_SORT``) was indexed twice
  under two doc ids, exercising duplicate removal.
* ``q_keyboard`` returns hits but none are relevant, and ``q_quantum`` returns
  nothing at all: the two flavours of "zero relevant".

All relevance is expressed against ``canonical_id`` (a content hash), never
against a raw doc id.
"""
from __future__ import annotations

import hashlib

INDEX = "ir-corpus-v1"


def canonical_id(body: str) -> str:
    return "C_" + hashlib.sha1(body.strip().encode()).hexdigest()[:10].upper()


def _doc(doc_id: str, title: str, body: str, tags: list[str]) -> dict:
    cid = canonical_id(body)
    return {
        "doc_id": doc_id,
        "canonical_id": cid,
        "content_hash": cid,
        "title": title,
        "body": body,
        "tags": tags,
    }


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
_TIE_A_BODY = (
    "docker network debugging recipes: inspect the bridge network, trace dns "
    "resolution, and verify docker port publishing before restarting the daemon"
)
# Same word multiset as _TIE_A_BODY (rearranged only) => identical BM25 score
# for any unigram query, while remaining a genuinely different document.
_TIE_B_BODY = (
    "docker network debugging recipes: trace the bridge network, verify dns "
    "resolution, and inspect docker port publishing before restarting the daemon"
)

_DUPE_SORT_BODY = (
    "python sort stability explained: sorted and list sort use timsort, which "
    "preserves the relative order of records with equal keys during merging runs"
)

DOCUMENTS: list[dict] = [
    # --- python: duplicate group + unjudged neighbour ---
    _doc(
        "py-sort-1",
        "python sort stability guide",
        _DUPE_SORT_BODY,
        ["python", "sorting"],
    ),
    _doc(
        # byte-identical body => same canonical id; deliberately indexed twice.
        "py-sort-2",
        "python sort stability guide",
        _DUPE_SORT_BODY,
        ["python", "sorting", "reindexed-copy"],
    ),
    _doc(
        "py-docs-9",
        "python api documentation conventions",
        "documenting a python library: write docstrings with examples, configure "
        "sphinx autodoc, and keep the sort order of api entries alphabetical",
        ["python", "docs"],
    ),
    _doc(
        "py-typing-12",
        "python typing with mypy",
        "adding gradual typing to a large python codebase using mypy and type "
        "hints, with protocols and generics for shared interfaces",
        ["python", "typing"],
    ),
    # --- networking: engineered tie ---
    _doc("net-debug-a", "docker network debugging notes", _TIE_A_BODY, ["docker", "network"]),
    _doc("net-debug-b", "docker network debugging notes", _TIE_B_BODY, ["docker", "network"]),
    _doc(
        "net-dns-3",
        "dns resolution in containers",
        "how containers resolve dns names through embedded resolvers and caching "
        "name servers, and why nsswitch can make localhost lookups fail",
        ["docker", "dns"],
    ),
    # title-only hit for the "publishing" query: baseline ranks it below the
    # body-rich dns doc; title boost moves it to rank 1 (a helped query).
    _doc(
        "net-publish-2",
        "docker port publishing troubleshooting",
        "mapping a service onto the host interface and reading startup warnings "
        "when it binds the wrong address",
        ["docker", "network"],
    ),
    _doc(
        "net-debug-long",
        "docker daemon logs",
        "docker port publishing troubleshooting guide: when publishing a port, "
        "inspect the host bindings, check which address docker is publishing to, "
        "and read the docker troubleshooting guide on port conflicts before "
        "restarting anything on the host network",
        ["docker", "network"],
    ),
    # --- databases ---
    _doc(
        "db-backup-4",
        "postgres backup and wal archiving",
        "postgres backup strategy: combine pg_dump logical backups with wal "
        "archive shipping for point in time recovery and regular restore drills",
        ["postgres", "backup"],
    ),
    _doc(
        "db-index-8",
        "choosing postgres index types",
        "choosing between btree, gin and brin postgres index types for range "
        "queries, jsonb columns and very large append only tables",
        ["postgres", "indexing"],
    ),
    # --- keyboards: hits exist but nothing is relevant to the judged query ---
    _doc(
        "kb-switch-5",
        "mechanical keyboard switch lube guide",
        "lubing mechanical keyboard switches with grease to smooth stock "
        "scratchiness and dampen the sound of long typing sessions",
        ["keyboard"],
    ),
    _doc(
        "kb-layout-6",
        "split keyboard layout design",
        "designing a split ergonomic keyboard layout with thumb clusters and "
        "columnar stagger for reduced wrist strain",
        ["keyboard"],
    ),
    # --- photography: title boost flips this pair ---
    _doc(
        "photo-astro-11",
        "field notes",
        "astrophotography stacking: register and integrate many light frames, "
        "subtract dark bias and flat calibration frames, and drive down read "
        "noise so faint signal survives the reduction",
        ["photography"],
    ),
    _doc(
        "photo-portrait-10",
        "astrophotography stacking and noise reduction checklist",
        "opinion piece on portrait lighting: flattering light beats gear, and "
        "sharp eyes matter more than megapixels in most sessions",
        ["photography"],
    ),
]

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
QUERIES: list[dict] = [
    {
        "query_id": "q_py_sort",
        "text": "python sort stability timsort",
        "title": "Python 排序稳定性",
        "scenario": "duplicate",
        "note": "同一规范文档被重复索引，验证去重不重复加分，并含一个未标注文档。",
    },
    {
        "query_id": "q_net_debug",
        "text": "docker network debugging",
        "title": "Docker 网络排查",
        "scenario": "tie",
        "note": "两篇不同文档 BM25 分值完全相同，按 doc_id 确定性打破并列；两者标注等级不同。",
    },
    {
        "query_id": "q_backup",
        "text": "postgres backup wal archive recovery",
        "title": "Postgres 备份恢复",
        "scenario": "normal",
        "note": "普通查询，用于观察标题加权后排名的常规变化。",
    },
    {
        "query_id": "q_publish",
        "text": "docker port publishing troubleshooting",
        "title": "Docker 端口发布",
        "scenario": "helped",
        "note": "相关文档命中主要在标题，标题加权后从第 2 升到第 1，展示“被帮助”的查询。",
    },
    {
        "query_id": "q_photo",
        "text": "astrophotography stacking noise reduction",
        "title": "天文摄影降噪",
        "scenario": "hurt",
        "note": "标题加权把标题党文档推到真正相关文档之前，展示“被伤害”的查询。",
    },
    {
        "query_id": "q_keyboard",
        "text": "ergonomic split keyboard wrist pain",
        "title": "人体工学键盘",
        "scenario": "zero_relevant_hits",
        "note": "有检索结果，但判断集里没有任何相关文档（全部 grade=0）。",
    },
    {
        "query_id": "q_quantum",
        "text": "quantum entanglement teleportation",
        "title": "量子纠缠",
        "scenario": "zero_hits",
        "note": "语料中完全没有匹配，检索结果为空且无相关文档。",
    },
]

# ---------------------------------------------------------------------------
# Judges and qrels (grades 0-3 against canonical_id)
# ---------------------------------------------------------------------------
JUDGES: list[dict] = [
    {"judge_id": "judge_alice", "name": "Alice", "team": "搜索质量组"},
    {"judge_id": "judge_bob", "name": "Bob", "team": "内容平台组"},
]

_CID = {d["doc_id"]: d["canonical_id"] for d in DOCUMENTS}

QRELS: list[dict] = [
    # q_py_sort: duplicate canonical doc is highly relevant; docs page marginal;
    # typing page is left *unjudged* on purpose (no row).
    {"query_id": "q_py_sort", "doc_id": _CID["py-sort-1"], "grade": 3,
     "judge_id": "judge_alice"},
    {"query_id": "q_py_sort", "doc_id": _CID["py-docs-9"], "grade": 1,
     "judge_id": "judge_alice"},
    {"query_id": "q_py_sort", "doc_id": _CID["py-typing-12"], "grade": 0,
     "judge_id": "judge_bob"},
    # tie pair: identical scores, intentionally different grades
    {"query_id": "q_net_debug", "doc_id": _CID["net-debug-a"], "grade": 2,
     "judge_id": "judge_bob"},
    {"query_id": "q_net_debug", "doc_id": _CID["net-debug-b"], "grade": 3,
     "judge_id": "judge_alice"},
    {"query_id": "q_net_debug", "doc_id": _CID["net-dns-3"], "grade": 0,
     "judge_id": "judge_bob"},
    {"query_id": "q_backup", "doc_id": _CID["db-backup-4"], "grade": 3,
     "judge_id": "judge_alice"},
    {"query_id": "q_backup", "doc_id": _CID["db-index-8"], "grade": 0,
     "judge_id": "judge_bob"},
    # publish: the title-focused publishing doc is the answer. The body-rich
    # debugging pair appears in this run but is judged off-topic for publishing;
    # title boost promotes the answer above them.
    {"query_id": "q_publish", "doc_id": _CID["net-publish-2"], "grade": 3,
     "judge_id": "judge_bob"},
    {"query_id": "q_publish", "doc_id": _CID["net-debug-a"], "grade": 0,
     "judge_id": "judge_alice"},
    {"query_id": "q_publish", "doc_id": _CID["net-debug-b"], "grade": 0,
     "judge_id": "judge_alice"},
    {"query_id": "q_publish", "doc_id": _CID["net-debug-long"], "grade": 0,
     "judge_id": "judge_alice"},
    # photo: the body-rich astro doc is the relevant one
    {"query_id": "q_photo", "doc_id": _CID["photo-astro-11"], "grade": 3,
     "judge_id": "judge_alice"},
    {"query_id": "q_photo", "doc_id": _CID["photo-portrait-10"], "grade": 0,
     "judge_id": "judge_bob"},
    # keyboard: hits exist, everything judged non-relevant
    {"query_id": "q_keyboard", "doc_id": _CID["kb-layout-6"], "grade": 0,
     "judge_id": "judge_alice"},
    {"query_id": "q_keyboard", "doc_id": _CID["kb-switch-5"], "grade": 0,
     "judge_id": "judge_bob"},
    # q_quantum: no qrel rows at all (no judgments, no relevant docs)
]

JUDGMENT_SET = {
    "set_id": "js-synth-v1",
    "name": "合成判断集 v1",
    "description": "本地合成文本的判断集，含零相关、并列分值与重复文档场景。",
    "version": "1.0.0",
}

# ---------------------------------------------------------------------------
# Run configurations and experiments
# ---------------------------------------------------------------------------
RUN_CONFIGS: list[dict] = [
    {
        "config_id": "rc-baseline-body",
        "name": "基线：title/body 等权 BM25",
        "description": "title 与 body 权重相同，OR 匹配。",
        "config": {"title_boost": 1.0, "body_boost": 1.0, "operator": "or",
                   "analyzer": "standard"},
    },
    {
        "config_id": "rc-title-boost",
        "name": "实验：标题加权 ×3",
        "description": "排序改动候选：title 字段 boost 提高到 3，其余不变。",
        "config": {"title_boost": 3.0, "body_boost": 1.0, "operator": "or",
                   "analyzer": "standard"},
    },
    {
        "config_id": "rc-strict-and",
        "name": "实验：AND 严格匹配（无基准）",
        "description": "改为 AND 匹配的另一次试验，故意不关联基准运行，用于展示缺失基准时不伪造提升。",
        "config": {"title_boost": 1.0, "body_boost": 1.0, "operator": "and",
                   "analyzer": "standard"},
    },
]

EXPERIMENTS: list[dict] = [
    {
        "experiment_id": "exp-title-boost",
        "name": "标题加权 ×3 评测",
        "description": "在同一索引快照上对比 title boost 1→3 的逐查询影响。",
        "treatment_config_id": "rc-title-boost",
        "baseline_config_id": "rc-baseline-body",
        "judgment_set_id": "js-synth-v1",
    },
    {
        "experiment_id": "exp-strict-and-standalone",
        "name": "AND 匹配试验（缺基准）",
        "description": "只运行了试验配置、没有对应基准运行，前端必须显示“无法比较”，不得给出虚假提升。",
        "treatment_config_id": "rc-strict-and",
        "baseline_config_id": None,
        "judgment_set_id": "js-synth-v1",
    },
]
