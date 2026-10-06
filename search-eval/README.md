# 搜索相关性评测平台

回答一个问题：**一次排序改动到底帮助了哪些查询？**——而不是只看平均点击率。

- **Vue 3**：实验列表 → 总体指标变化 → 逐查询对照 → 单查询排名下钻
- **FastAPI**：调用 `pytrec_eval` 计算指标，所有评测策略显式声明
- **PostgreSQL**：保存判断集（含判断者、版本）、实验与运行产物
- **OpenSearch**：本地单节点，提供可复现检索

## 评测策略（显式约定）

| 项目 | 约定 |
|---|---|
| 截断 | 所有指标在 **rank 10** 截断（检索深度 20，评分前截断） |
| NDCG@10 | `ndcg_cut.10`，线性增益（gain = 标注等级）；IDCG 取该查询全部已标注文档的理想排序 |
| MRR@10 | 截断后 run 上的 `recip_rank`；等级 ≥ 1 视为相关 |
| Recall@10 | 分母 = 该查询已标注相关（等级 ≥ 1）文档数；**零相关查询不参与 Recall 平均**（接口返回 `recall_query_count` 说明实际计入的查询数），但仍以 0 分计入 NDCG/MRR 平均 |
| 未标注文档 | 一律按 0 级（不相关）处理——trec_eval 标准池化假设 |
| 重复文档 | 评分前按逻辑 `doc_id` 去重，保留最高名次；同一文档**不会重复加分** |
| 并列分值 | 得分相同按 `doc_id` 字典序降序（trec_eval 约定），与输入顺序无关 |

策略常量见 `backend/app/metrics.py`，运行时可从 `GET /api/metric-policy` 读取，
前端每个页面底部也会展示。

## 数据模型（PostgreSQL）

- `judges`：判断者，与判断集版本分离，每条判断记录判断者
- `judgment_sets` / `judgments`：按 `(name, version)` 冻结的判断集；`(set, query, doc)` 唯一
- `experiments`：绑定判断集版本、索引名、基准/处理两份查询配置（JSON）
- `runs`：每个实验每角色（baseline/treatment）至多一条；**运行产物绑定索引与查询配置快照**
- `run_results`：原始检索行，含被去重/截断丢弃的行（`kept=false` + 原因），保证下钻透明
- `query_metrics`：逐查询指标

**不伪造提升**：`/compare` 与下钻接口在基准或处理运行缺失时返回 **409**，
前端显示"缺少运行"横幅而不是估计值。

## 合成语料（本地、可复现）

`backend/app/seed.py` 生成 36 篇咖啡主题合成文档、10 个查询、47 条判断（两名判断者），刻意包含：

- **q06**：所有候选标注为 0 —— 零相关查询
- **d30/d31**：标题正文完全相同 —— BM25 得分并列
- **d12**：同一逻辑文档被索引两次（重灌重复）—— 检索结果中会出现两次，评分前去重

种子含两个实验：`title-boost-v2`（基准 match vs 处理 title^3 加权，均已真实运行）；
`phrase-ranking`（未运行，用于演示 409 护栏）。

## 运行

```bash
scripts/start_infra.sh       # PostgreSQL :5432 + OpenSearch :9200（用户态，无需 root）
scripts/seed.sh              # 建索引、写判断集、执行演示运行
scripts/build_frontend.sh    # 构建 Vue 前端到 frontend/dist
scripts/run_backend.sh       # FastAPI :8000（同时托管 API 与前端）
```

打开 http://localhost:8000 → 实验 → `title-boost-v2` → 点击任意查询行下钻。

前端开发模式：`cd frontend && npm run dev`（:5173，代理 /api 到 :8000）。

## API 摘要

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/metric-policy` | 当前评测策略 |
| GET | `/api/queries` · `/api/judgment-sets[/{id}]` | 查询与判断集（含判断者） |
| GET/POST | `/api/experiments[/{id}]` | 实验列表/详情/创建 |
| POST | `/api/experiments/{id}/runs/{baseline\|treatment}` | 执行检索+评分，覆盖旧运行 |
| GET | `/api/experiments/{id}/compare` | 总体与逐查询对照；缺运行返回 409 |
| GET | `/api/experiments/{id}/queries/{qid}` | 单查询双栏排名下钻（含去重/截断/未标注标记） |

## 测试

```bash
cd backend && ../.venv/bin/python -m pytest tests/ -q
```

12 个用例覆盖：去重不重复加分、零相关查询的 Recall 排除、未标注按 0 级、
截断位置、MRR 倒数名次、并列分值顺序无关、缺运行 409 护栏、端到端运行与对照。

## 环境说明

本工作区为 aarch64 无 root 环境：PostgreSQL 17.5 使用 zonky 自包含二进制
（`/workspace/.infra/postgres`），OpenSearch 2.13.0 官方 arm64 包
（`/workspace/.infra/opensearch`，已关闭安全插件、单节点）。
`docker-compose.yml` 提供有 Docker 环境下的等价参考部署。
`pytrec-eval-terrier` 在 aarch64 无预编译 wheel，已从源码编译
（Python 头文件解包于 `/workspace/.infra/pydev` 并复制进 venv）。
