<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'
import { fmtMetric, fmtDelta } from '../format.js'
import QueryDrilldown from './QueryDrilldown.vue'

const experiments = ref([])
const selectedId = ref(null)
const comparison = ref(null)
const detailQuery = ref(null)
const scenarioFilter = ref('all')

const METRICS = [
  { key: 'ndcg_at_10', label: 'NDCG@10' },
  { key: 'mrr_at_10', label: 'MRR@10' },
  { key: 'recall_at_100', label: 'Recall@100' },
  { key: 'judged_at_10', label: 'Judged@10' },
]

async function load() {
  experiments.value = await api.experiments()
  if (!selectedId.value && experiments.value.length) {
    await select(experiments.value[0].experiment_id)
  } else if (selectedId.value) {
    await select(selectedId.value)
  }
}

async function select(id) {
  selectedId.value = id
  detailQuery.value = null
  comparison.value = await api.comparison(id)
}

function deltaCell(row, key) {
  const d = row.deltas ? fmtDelta(row.deltas[key]) : null
  if (!d) return { text: '无法比较', cls: 'na' }
  return d
}

const SCENARIOS = [
  { v: 'all', t: '全部' },
  { v: 'helped', t: '被帮助 ↑' },
  { v: 'hurt', t: '被伤害 ↓' },
  { v: 'normal', t: '无变化' },
  { v: 'duplicate', t: '重复文档' },
  { v: 'tie', t: '并列分值' },
  { v: 'zero_relevant_hits', t: '零相关(有结果)' },
  { v: 'zero_hits', t: '零命中' },
]

function rowScenario(row) {
  if (!row.deltas) return 'na'
  const mrr = row.deltas.mrr_at_10
  const ndcg = row.deltas.ndcg_at_10
  const best = Math.max(Math.abs(mrr ?? 0), Math.abs(ndcg ?? 0))
  if (best < 1e-9) return row.scenario === 'normal' ? 'normal' : 'other'
  return (mrr ?? ndcg) > 0 ? 'helped' : 'hurt'
}

function visibleRows() {
  if (!comparison.value) return []
  const rows = comparison.value.per_query
  if (scenarioFilter.value === 'all') return rows
  if (scenarioFilter.value === 'helped' || scenarioFilter.value === 'hurt') {
    return rows.filter(r => rowScenario(r) === scenarioFilter.value)
  }
  if (scenarioFilter.value === 'normal') {
    return rows.filter(r => r.scenario === 'normal')
  }
  return rows.filter(r => r.scenario === scenarioFilter.value)
}

onMounted(load)
</script>

<template>
  <div>
    <!-- experiment picker -->
    <div class="panel">
      <div class="filters">
        <strong style="margin-right:6px">实验：</strong>
        <button v-for="e in experiments" :key="e.experiment_id"
                :class="{active: e.experiment_id===selectedId}"
                @click="select(e.experiment_id)">
          {{ e.name }}
        </button>
      </div>
      <div v-if="comparison" class="small muted">
        索引快照 <code>{{ comparison.experiment.index_name }}</code> ·
        判断集 <code>{{ comparison.experiment.judgment_set_id }}</code> ·
        运行角色：{{ comparison.roles.join('、') }}
      </div>
    </div>

    <template v-if="comparison">
      <!-- missing baseline guard -->
      <div v-if="comparison.baseline_missing" class="notice">
        该实验只运行了试验配置，<strong>缺少基准运行</strong>。下方只展示试验配置自身的指标，
        所有“提升幅度”位置一律显示「无法比较」，系统不会用 0 或历史均值伪造基准。
      </div>

      <!-- aggregate -->
      <div class="panel">
        <h2>总体变化（宏平均）</h2>
        <div class="metric-cards">
          <div class="metric-card" v-for="m in METRICS" :key="m.key">
            <div class="label">{{ m.label }}</div>
            <div class="value">
              {{ comparison.baseline_missing
                  ? fmtMetric(comparison.aggregate.treatment?.[m.key])
                  : fmtMetric(comparison.aggregate.treatment?.[m.key]) }}
            </div>
            <div v-if="!comparison.baseline_missing" class="delta" :class="fmtDelta(comparison.aggregate_deltas?.[m.key])?.cls">
              基准 {{ fmtMetric(comparison.aggregate.baseline?.[m.key]) }}
              → {{ fmtDelta(comparison.aggregate_deltas?.[m.key])?.text }}
            </div>
            <div v-else class="delta na">无基准 · 无法比较</div>
          </div>
        </div>
        <div class="legend">
          <span>查询数 {{ comparison.aggregate.treatment ? '' : '' }}</span>
          <span>零相关查询的指标为 <code>null</code>，不计入均值（区别于命中为 0）</span>
          <span>缺失运行补空运行（0 分）计入均值</span>
        </div>
      </div>

      <!-- per query table -->
      <div class="panel">
        <h2>逐查询下钻</h2>
        <div class="filters">
          <span class="muted small">筛选：</span>
          <button v-for="s in SCENARIOS" :key="s.v"
                  :class="{active: scenarioFilter===s.v}"
                  @click="scenarioFilter=s.v">{{ s.t }}</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>查询</th>
              <th>场景</th>
              <th class="num">相关数</th>
              <th class="num">NDCG@10 基准→实验</th>
              <th class="num">Δ</th>
              <th class="num">MRR@10 基准→实验</th>
              <th class="num">Δ</th>
              <th class="num">Recall@100 Δ</th>
              <th class="num">重复丢弃</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in visibleRows()" :key="r.query_id" class="clickable"
                :style="detailQuery===r.query_id ? 'background:#1d273a' : ''"
                @click="detailQuery = detailQuery===r.query_id ? null : r.query_id">
              <td>
                <div><strong>{{ r.title }}</strong></div>
                <div class="muted small">{{ r.query_id }}</div>
              </td>
              <td class="small">{{ r.scenario }}</td>
              <td class="num">{{ r.treatment?.num_relevant }}</td>
              <td class="num">
                {{ r.baseline ? fmtMetric(r.baseline.ndcg_at_10)+' → '+fmtMetric(r.treatment.ndcg_at_10)
                              : fmtMetric(r.treatment.ndcg_at_10)+' （无基准）' }}
              </td>
              <td class="num" :class="deltaCell(r,'ndcg_at_10').cls">{{ deltaCell(r,'ndcg_at_10').text }}</td>
              <td class="num">
                {{ r.baseline ? fmtMetric(r.baseline.mrr_at_10)+' → '+fmtMetric(r.treatment.mrr_at_10)
                              : fmtMetric(r.treatment.mrr_at_10)+' （无基准）' }}
              </td>
              <td class="num" :class="deltaCell(r,'mrr_at_10').cls">{{ deltaCell(r,'mrr_at_10').text }}</td>
              <td class="num" :class="deltaCell(r,'recall_at_100').cls">{{ deltaCell(r,'recall_at_100').text }}</td>
              <td class="num">{{ r.treatment?.duplicates_dropped ?? 0 }}</td>
            </tr>
          </tbody>
        </table>
        <div class="small muted" style="margin-top:8px">点击任意查询行，展开基准 vs 实验的具体排名对照。</div>
      </div>

      <!-- drilldown -->
      <QueryDrilldown v-if="detailQuery"
                      :experiment-id="selectedId"
                      :query-id="detailQuery"
                      @close="detailQuery=null" />
    </template>
  </div>
</template>
