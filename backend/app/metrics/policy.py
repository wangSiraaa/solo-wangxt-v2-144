"""Metric policy: the single source of truth for *how* metrics are defined.

The UI renders the descriptions returned here so that denominators, cutoffs and
the unjudged-document policy are never left implicit.
"""
from __future__ import annotations

# Grade labels used in the judged set (0-3 scale).
GRADE_LABELS: dict[int, str] = {
    0: "不相关",
    1: "勉强相关",
    2: "相关",
    3: "高度相关",
}

# Grades at or above this threshold count as "relevant" for binary metrics
# (MRR, recall, precision).
REL_THRESHOLD = 1

CUTOFFS = {
    "ndcg": 10,       # NDCG@10
    "mrr": 10,        # MRR@10
    "recall": 100,    # Recall@100
    "judged": 10,     # supporting measure: judged coverage in the top-10
    "p_at_1": 1,
}

POLICY = [
    {
        "key": "ndcg_cut_10",
        "display": "NDCG@10",
        "family": "graded",
        "cutoff": 10,
        "numerator": "前 10 个位置的折损累计增益 DCG，相关度增益为 2^grade − 1，位置 p 的折损为 1/log2(p+1)",
        "denominator": "由该查询判断集中的相关文档构成的理想排序 IDCG@10",
        "range": "[0, 1]，1 表示前 10 名与理想排序一致",
        "unjudged": "未标注文档按增益 0 处理（不进入理想排序 IDCG），即“非贪婪”策略",
        "empty_query": "判断集中没有任何相关文档时该值无定义，记为 null（原始 trec_eval 数值为 0，单列为 0_rel 原始值便于核对）",
        "duplicates": "同一规范文档（canonical_id）在前 10 中重复出现只计一次，保留最高得分与最靠前位置",
    },
    {
        "key": "recip_rank_cut_10",
        "display": "MRR@10",
        "family": "binary",
        "cutoff": 10,
        "numerator": "1 / rank(first relevant doc)，相关定义为 grade ≥ 1；前 10 名无相关文档则为 0",
        "denominator": "每个查询固定为 1；宏平均时除以查询数（包括零命中查询）",
        "range": "[0, 1]",
        "unjudged": "未标注文档视为不相关，不会作为第一个相关文档",
        "empty_query": "判断集无相关文档时无定义，记为 null，不并入平均",
        "duplicates": "先按规范文档去重再在去重后的序列上找首个相关位置",
    },
    {
        "key": "recall_100",
        "display": "Recall@100",
        "family": "binary",
        "cutoff": 100,
        "numerator": "前 100 名中出现的、grade ≥ 1 的不同规范文档数",
        "denominator": "该查询判断集中 grade ≥ 1 的不同规范文档总数",
        "range": "[0, 1]",
        "unjudged": "未标注文档既不计入分子也不计入分母；召回率只对已判断的相关文档负责",
        "empty_query": "分母为 0（判断集无相关文档）时无定义，记为 null",
        "duplicates": "分子按去重后的规范文档计数；同一文档被检索到多次不增加分子",
    },
    {
        "key": "judged_10",
        "display": "Judged@10",
        "family": "coverage",
        "cutoff": 10,
        "numerator": "前 10 名中在判断集里出现过（含 grade=0）的文档数",
        "denominator": "10",
        "range": "[0, 1]，用于判断 NDCG/MRR 的结论是否受大量未标注文档影响",
        "unjudged": "这是唯一专门衡量未标注比例的指标",
        "empty_query": "正常计算（与是否有相关文档无关）",
        "duplicates": "按去重后的前 10 个不同文档计算",
    },
]

# How aggregate means are formed.
AGGREGATION_POLICY = (
    "宏平均（macro average）：每个查询等权，先逐查询计算指标，再对有定义的查询取算术平均。"
    " 运行完全缺失的查询补为空运行（各指标 0）参与平均；判断集无相关文档的查询为 null，不计入均值。"
)


def policy_payload() -> dict:
    return {
        "grade_labels": GRADE_LABELS,
        "rel_threshold": REL_THRESHOLD,
        "cutoffs": CUTOFFS,
        "metrics": POLICY,
        "aggregation": AGGREGATION_POLICY,
        "tie_breaking": (
            "两层并列处理，必须区分：(1) 展示/去重层——检索端固定 _score 降序、_id 升序排序，"
            "评测端再按 (score 降序, doc_id 升序) 稳定排序，保证界面排名与去重位置可复现、不依赖随机或插入顺序；"
            "(2) 指标层——送入 pytrec_eval（trec_eval 9.0）后，同分值文档被视为一个无序“并列块”，"
            "NDCG 对块内各位置的折损取平均、MRR 对块内各位置的倒数排名取平均。因此并列文档之间的先后"
            "不会改变指标；只有分值真正被拉开时，doc_id 顺序才会通过排名影响指标。q_net_debug 就是这一语义的示例。"
        ),
        "unjudged_strategy": "non_greedy",  # pytrec_eval / trec_eval default
        "dedup": (
            "规范文档 ID（canonical_id，按正文内容哈希）为评测单位。原始结果先按 canonical_id 去重："
            "同一文档保留最高得分及其最靠前位置，重复项仍在排名对照中标出但不重复加分。"
        ),
    }
