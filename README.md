# IR 排序评测台（本地、可复现）

回答搜索团队的问题：**一次排序改动到底帮助（和伤害）了哪些查询**，而不是只看平均点击率。
从总体指标变化逐层下钻到每个查询的具体排名，所有数据均为本地合成文本，可重复执行。

## 技术栈

| 层 | 技术 | 作用 |
|---|---|---|
| 前端 | Vue 3 + Vite（Composition API，原生 CSS） | 实验总览 → 逐查询 → 排名对照下钻；查询/标注；指标口径；即时检索 |
| 后端 | FastAPI | REST API、实验编排 |
| 指标 | **pytrec_eval**（trec_eval 9.0 绑定） | NDCG@10、MRR@10、Recall@100、Judged@10 |
| 存储 | PostgreSQL | 判断者、判断集版本、查询、qrels、查询配置、实验、运行、排名与指标 |
| 检索 | 本地 OpenSearch 2.19（单节点、安全插件关闭） | 可复现 BM25 检索 |

## 明确的指标口径（与代码、UI 完全一致）

- **NDCG@10**：DCG 增益 `2^grade−1`、折损 `1/log2(p+1)`；分母是该查询判断集相关文档构成的 **IDCG@10**。
- **MRR@10**：先把运行截断到前 10，再取首个 grade≥1 文档位置的倒数（trec_eval 的 `recip_rank` 本身没有截断参数，所以截断在调用前完成）。
- **Recall@100**：分子=前 100 名中 grade≥1 的**不同规范文档数**；分母=判断集中 grade≥1 的不同规范文档总数（不是语料总数）。
- **未标注文档**：non-greedy 策略——增益按 0 处理，且**不进入 IDCG**；不计入召回分母。另用 **Judged@10** 单独暴露标注覆盖度。
- **零相关查询**（判断集没有任何相关文档）：NDCG/MRR/Recall **无定义 → `null`**，不计入均值；同时保留 trec_eval 的原始数值 0 供核对。两种零结果分开处理：`q_keyboard`（有结果但全 grade=0）与 `q_quantum`（完全无命中、无标注）。
- **缺失运行**：qrels 里有、运行里没有的查询补为**空运行（0 分）参与平均**，不会被静默丢弃。
- **重复文档**：以正文内容哈希 `canonical_id` 为评测单位；同一规范文档出现多次**只计一次**（保留最高分、最靠前位置），副本在排名对照中标“重复·不计分”。
- **并列分值（两层，务必区分）**：
  - 展示/去重层：固定 `_score 降序、_id 升序`，单分片，排名可复现；
  - 指标层：trec_eval 把同分值文档视为无序块，**NDCG 对块内折损取平均、MRR 对块内倒数排名取平均**，所以并列文档的先后不改变指标。`q_net_debug` 是示例。
- **宏平均**：每查询等权，先逐查询算指标，再对有定义的查询取算术平均。

## 数据模型的关键隔离

- **判断者（judges）与实验版本分离**：标注归属判断者；实验/运行配置是另一组版本对象，同一份判断集可被多实验复用。
- **运行绑定索引与查询配置**：`experiments` 冻结索引名、settings/mapping 快照；`runs` 冻结当时的查询配置 JSON，保证可复现。
- **缺少基准运行不伪造提升**：`exp-strict-and-standalone` 只有实验运行，其所有 delta 为 `null`，UI 显示“无法比较”，绝不当作 0 或历史均值。

## 合成语料内置的对抗场景（14 篇 / 7 查询）

| 查询 | 场景 |
|---|---|
| `q_publish` | 标题加权后相关文档从第 2 升到第 1（**被帮助**） |
| `q_photo` | 标题党文档被推到真正相关文档之前（**被伤害**） |
| `q_py_sort` | 同一规范文档被索引两次（重复，不重复加分）+ 未标注文档 |
| `q_net_debug` | 两篇不同文档 BM25 分值完全相同（并列块，标注等级不同） |
| `q_keyboard` | 有检索结果但全部 grade=0（零相关） |
| `q_quantum` | 语料无匹配（零命中、无标注） |
| `q_backup` | 常规查询 |

实验对比：基线 `title/body 等权` → 实验 `title boost ×3`，总体 NDCG 均值几乎不变，但逐查询可见明显的一升一降——这正是只看平均值会掩盖的信息。

## 目录

```
backend/
  app/
    config.py db.py            # 配置与连接
    schema.sql                 # PostgreSQL 结构
    data/corpus.py             # 合成语料/查询/qrels/配置/实验
    search/client.py           # OpenSearch 索引与检索（固定并列排序）
    metrics/policy.py          # 指标口径（单一事实来源，UI 直接渲染）
    metrics/dedup.py           # 确定性排序 + canonical_id 去重
    metrics/evaluator.py       # pytrec_eval 封装、零相关/缺失处理
    metrics/delta.py           # 基准 vs 实验对比（缺基准 → null）
    services.py seed.py        # 实验编排与幂等播种
    main.py                    # FastAPI
  tests/                       # 13 单元 + 5 集成（需本地服务）
frontend/                      # Vue 3 + Vite
scripts/                       # 本地服务启动/停止辅助
```

## 快速开始（本机已装 Python 3.11 与 Node 20）

```bash
# 1) 依赖（在已准备好的虚拟环境中）
backend:  pip install -r backend/requirements.txt
frontend: cd frontend && npm install

# 2) 初始化 PostgreSQL 与 OpenSearch（若尚未运行）
scripts/start_services.sh

# 3) 建表 + 写入语料 + 建索引 + 运行全部实验
cd backend && python -m app.seed

# 4) 启动后端
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 5) 启动前端（开发，自动代理 /api）
cd frontend && npm run dev          # http://127.0.0.1:5173
# 或构建后由 FastAPI 单端口提供：
#   cd frontend && npm run build
#   IREVAL_FRONTEND_DIST=../frontend/dist uvicorn app.main:app --port 8000
```

## 测试

```bash
cd backend
pytest tests/                                  # 仅纯函数单测
IREVAL_RUN_INTEGRATION=1 pytest tests/         # 加本地实时服务集成测试
```

## 主要 API

- `GET /api/policy` 指标口径（分母/截断/未标注/重复/并列）
- `GET /api/experiments`、`GET /api/experiments/{id}/comparison`
- `GET /api/experiments/{id}/queries/{qid}` 逐查询指标 delta + 两侧排名
- `GET /api/queries` 查询与其 qrels（含判断者）、`GET /api/judges`
- `POST /api/search` 用任意配置即时检索（playground）
