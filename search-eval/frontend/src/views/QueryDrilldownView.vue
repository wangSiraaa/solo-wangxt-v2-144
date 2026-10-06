<template>
  <div v-if="data">
    <p><RouterLink :to="`/experiments/${id}`">← 返回实验</RouterLink></p>
    <h2>{{ data.text }} <span class="muted mono">({{ data.query_id }})</span></h2>

    <div class="card-row">
      <div class="card" v-for="side in ['baseline', 'treatment']" :key="side">
        <h4>{{ side === 'baseline' ? '基准' : '处理' }} ·
          <span class="mono">{{ JSON.stringify(data[side].query_config) }}</span></h4>
        <div v-if="data[side].metrics">
          NDCG@10 {{ fmt(data[side].metrics.ndcg) }} ·
          MRR@10 {{ fmt(data[side].metrics.mrr) }} ·
          Recall@10 {{ data[side].metrics.recall == null ? '无相关文档' : fmt(data[side].metrics.recall) }}
        </div>
      </div>
    </div>

    <div class="split">
      <div v-for="side in ['baseline', 'treatment']" :key="side">
        <h3>{{ side === 'baseline' ? '基准排名' : '处理排名' }}</h3>
        <table>
          <thead>
            <tr><th>#</th><th>文档</th><th>得分</th><th>标注</th><th>变化</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in data[side].results" :key="row.rank"
                :class="{ 'row-dropped': !row.kept }">
              <td>{{ row.rank }}</td>
              <td class="mono">{{ row.doc_id }}</td>
              <td class="mono">{{ row.score.toFixed(4) }}
                <span v-if="isTie(side, row)" class="tag">并列</span></td>
              <td><GradeBadge :grade="row.grade" /></td>
              <td>
                <span v-if="!row.kept" class="muted">
                  {{ row.drop_reason === 'duplicate' ? '重复，不计分' : '超出截断' }}
                </span>
                <Movement v-else :value="data.movement[row.doc_id]" />
              </td>
            </tr>
            <tr v-if="!data[side].results.length">
              <td colspan="5" class="muted">该查询未检索到任何文档</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="policy" v-if="data.policy">
      <b>评测策略</b>
      <ul>
        <li v-for="(v, k) in data.policy" :key="k"><b>{{ k }}</b>: {{ v }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import GradeBadge from '../components/GradeBadge.vue'
import Movement from '../components/Movement.vue'

const props = defineProps({
  id: { type: String, required: true },
  qid: { type: String, required: true },
})

const data = ref(null)

function fmt(v) { return v == null ? '—' : v.toFixed(4) }

// A doc ties when a neighbour in the same ranking has the identical score.
function isTie(side, row) {
  const rows = data.value[side].results
  return rows.some((r) => r !== row && r.score === row.score)
}

onMounted(async () => {
  data.value = await api.drilldown(props.id, props.qid)
})
</script>
