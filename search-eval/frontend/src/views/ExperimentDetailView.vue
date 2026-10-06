<template>
  <div v-if="exp">
    <h2>{{ exp.name }}</h2>
    <p class="muted">
      判断集 <b>{{ exp.judgment_set }}</b> · 索引 <span class="mono">{{ exp.index_name }}</span>
    </p>
    <p>
      基准配置 <span class="mono">{{ JSON.stringify(exp.baseline_config) }}</span><br />
      处理配置 <span class="mono">{{ JSON.stringify(exp.treatment_config) }}</span>
    </p>

    <div v-if="missing.length" class="banner">
      缺少{{ missingText }}运行，无法计算提升幅度——平台不会用估计值代替真实基准。
      <button :disabled="running" @click="runMissing">运行缺失项</button>
      <span v-if="runError" class="delta-neg"> {{ runError }}</span>
    </div>

    <template v-if="compare">
      <div class="card-row">
        <div class="card" v-for="m in metricCards" :key="m.key">
          <h4>{{ m.label }}</h4>
          <div class="nums">
            {{ fmt(compare.aggregate.baseline[m.key]) }}
            → {{ fmt(compare.aggregate.treatment[m.key]) }}
            <Delta :value="compare.aggregate.delta[m.key]" />
          </div>
        </div>
      </div>
      <p class="muted">
        共 {{ compare.aggregate.baseline.num_queries }} 个查询；Recall@10 仅在
        {{ compare.aggregate.baseline.recall_query_count }} 个有相关文档的查询上取平均；
        处理运行去除了 {{ compare.aggregate.treatment.duplicates_removed }} 条重复文档。
      </p>

      <h3>逐查询对照（点击行下钻到具体排名）</h3>
      <table>
        <thead>
          <tr>
            <th>查询</th>
            <th class="sortable" @click="sortBy('num_rel')">相关文档数 {{ arrow('num_rel') }}</th>
            <th v-for="m in metricCards" :key="m.key" class="sortable"
                @click="sortBy(m.key)">
              Δ {{ m.label }} {{ arrow(m.key) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sortedRows" :key="row.query_id" class="clickable"
              @click="$router.push(`/experiments/${exp.id}/queries/${row.query_id}`)">
            <td>{{ row.text }} <span class="muted mono">({{ row.query_id }})</span>
              <span v-if="row.num_rel === 0" class="tag">零相关</span></td>
            <td>{{ row.num_rel }}</td>
            <td v-for="m in metricCards" :key="m.key">
              <span class="muted">{{ fmt(row.baseline[m.key]) }} →
                {{ fmt(row.treatment[m.key]) }}</span>
              <Delta :value="row.delta[m.key]" />
            </td>
          </tr>
        </tbody>
      </table>
    </template>

    <div class="policy" v-if="policy">
      <b>评测策略</b>
      <ul>
        <li v-for="(v, k) in policy" :key="k"><b>{{ k }}</b>: {{ v }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import Delta from '../components/Delta.vue'

const props = defineProps({ id: { type: String, required: true } })

const exp = ref(null)
const compare = ref(null)
const policy = ref(null)
const running = ref(false)
const runError = ref('')
const sortKey = ref('ndcg')
const sortDir = ref(-1)

const metricCards = [
  { key: 'ndcg', label: 'NDCG@10' },
  { key: 'mrr', label: 'MRR@10' },
  { key: 'recall', label: 'Recall@10' },
]

const missing = computed(() => {
  if (!exp.value) return []
  const m = []
  if (exp.value.baseline?.status !== 'completed') m.push('baseline')
  if (exp.value.treatment?.status !== 'completed') m.push('treatment')
  return m
})
const missingText = computed(() =>
  missing.value.map((r) => (r === 'baseline' ? '基准' : '处理')).join('与'))

const sortedRows = computed(() => {
  if (!compare.value) return []
  const rows = [...compare.value.queries]
  rows.sort((a, b) => {
    const av = sortKey.value === 'num_rel' ? a.num_rel : a.delta[sortKey.value]
    const bv = sortKey.value === 'num_rel' ? b.num_rel : b.delta[sortKey.value]
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    return (av - bv) * sortDir.value
  })
  return rows
})

function fmt(v) { return v == null ? '—' : v.toFixed(4) }
function sortBy(key) {
  if (sortKey.value === key) sortDir.value *= -1
  else { sortKey.value = key; sortDir.value = key === 'num_rel' ? -1 : -1 }
}
function arrow(key) { return sortKey.value === key ? (sortDir.value < 0 ? '▼' : '▲') : '' }

async function load() {
  exp.value = await api.experiment(props.id)
  policy.value = await api.metricPolicy()
  compare.value = null
  if (!missing.value.length) {
    compare.value = await api.compare(props.id)
  }
}

async function runMissing() {
  running.value = true
  runError.value = ''
  try {
    for (const role of missing.value) {
      await api.runExperiment(props.id, role)
    }
    await load()
  } catch (e) {
    runError.value = e.message
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>
