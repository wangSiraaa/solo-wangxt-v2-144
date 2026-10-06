<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api.js'
import { fmtMetric, fmtDelta, gradeBadge } from '../format.js'

const props = defineProps({
  experimentId: String,
  queryId: String,
})
defineEmits(['close'])

const detail = ref(null)
const cutoff = 10

async function load() {
  detail.value = await api.queryDetail(props.experimentId, props.queryId)
}
onMounted(load)
watch(() => props.queryId, load)

const roles = () => detail.value ? Object.keys(detail.value.rankings) : []
</script>

<template>
  <div class="panel" v-if="detail">
    <div class="breadcrumb">
      <a @click="$emit('close')">← 返回逐查询列表</a>
    </div>

    <div class="query-head">
      <h2 style="margin:0">{{ detail.query.title }}</h2>
      <span class="badge tag">{{ detail.query.scenario }}</span>
      <span class="muted small">{{ detail.query.text }}</span>
    </div>
    <p class="small muted" style="margin:4px 0 12px">{{ detail.query.note }}</p>

    <div v-if="detail.baseline_missing" class="notice">
      该实验没有基准运行，下列只显示实验排名；指标差值标记为「无法比较」。
    </div>

    <!-- per-query metric deltas -->
    <div class="metric-cards" style="margin-bottom:14px">
      <div class="metric-card">
        <div class="label">NDCG@10</div>
        <div class="value">{{ fmtMetric(detail.metrics.treatment?.ndcg_at_10) }}</div>
        <div class="delta" :class="detail.metric_deltas ? fmtDelta(detail.metric_deltas.ndcg_at_10)?.cls : 'na'">
          <template v-if="detail.metric_deltas">
            基准 {{ fmtMetric(detail.metrics.baseline?.ndcg_at_10) }} · {{ fmtDelta(detail.metric_deltas.ndcg_at_10)?.text }}
          </template>
          <template v-else>无法比较</template>
        </div>
      </div>
      <div class="metric-card">
        <div class="label">MRR@10（首个相关位置）</div>
        <div class="value">{{ fmtMetric(detail.metrics.treatment?.mrr_at_10) }}</div>
        <div class="delta" :class="detail.metric_deltas ? fmtDelta(detail.metric_deltas.mrr_at_10)?.cls : 'na'">
          <template v-if="detail.metric_deltas">
            基准 {{ fmtMetric(detail.metrics.baseline?.mrr_at_10) }} · {{ fmtDelta(detail.metric_deltas.mrr_at_10)?.text }}
          </template>
          <template v-else>无法比较</template>
        </div>
      </div>
      <div class="metric-card">
        <div class="label">Recall@100</div>
        <div class="value">{{ fmtMetric(detail.metrics.treatment?.recall_at_100) }}</div>
        <div class="delta" :class="detail.metric_deltas ? fmtDelta(detail.metric_deltas.recall_at_100)?.cls : 'na'">
          <template v-if="detail.metric_deltas">
            基准 {{ fmtMetric(detail.metrics.baseline?.recall_at_100) }} · {{ fmtDelta(detail.metric_deltas.recall_at_100)?.text }}
          </template>
          <template v-else>无法比较</template>
        </div>
      </div>
      <div class="metric-card">
        <div class="label">相关文档数 / 已返回 / 重复丢弃</div>
        <div class="value">
          {{ detail.metrics.treatment?.num_relevant }} /
          {{ detail.metrics.treatment?.num_returned }} /
          {{ detail.metrics.treatment?.duplicates_dropped }}
        </div>
        <div class="delta muted small">
          分母=判断集中 grade≥1 的不同规范文档数
        </div>
      </div>
    </div>

    <!-- side by side rankings -->
    <div class="ranking-grid">
      <div class="rank-col" v-for="role in roles()" :key="role">
        <h4>{{ role === 'baseline' ? '基准运行' : '实验运行' }}</h4>
        <div v-if="!detail.rankings[role].length" class="muted small">该查询无检索结果（空运行）。</div>
        <div v-for="h in detail.rankings[role]" :key="h.rank"
             class="doc-row"
             :class="{dup: h.duplicate, cutoff: h.rank>cutoff && !h.duplicate}"
             :style="h.duplicate ? '' : (h.rank>cutoff ? 'opacity:.55' : '')">
          <div class="doc-rank">
            {{ h.duplicate ? '⧗' : h.rank }}
            <div class="small" v-if="h.raw_rank && h.raw_rank!==h.rank && !h.duplicate">原{{ h.raw_rank }}</div>
          </div>
          <div class="doc-body">
            <div class="doc-title">{{ h.doc_id }}</div>
            <div class="doc-text small muted">规范 ID {{ h.canonical_doc_id }}</div>
            <div class="doc-meta">
              <span class="badge" :class="gradeBadge(h.grade).cls">{{ gradeBadge(h.grade).text }}</span>
              <span class="score">score {{ h.score.toFixed(3) }}</span>
              <span v-if="h.tied" class="badge tie">并列分值</span>
              <span v-if="h.duplicate" class="badge dup">重复 {{ h.canonical_doc_id }} · 不计分</span>
              <span v-if="h.duplicate" class="muted small">原始位置 {{ h.raw_rank }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="legend">
      <span>前 {{ cutoff }} 名参与 NDCG@10 / MRR@10；Recall@100 看前 100。</span>
      <span><span class="badge dup">重复</span> 同一规范文档的副本，去重后不重复加分。</span>
      <span><span class="badge tie">并列分值</span> trec_eval 对同分组按块平均，顺序不影响指标。</span>
    </div>
  </div>
</template>
