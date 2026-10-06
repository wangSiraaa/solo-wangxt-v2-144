<template>
  <div>
    <h2>实验</h2>
    <p class="muted">
      每个实验绑定一个冻结的判断集版本、一个索引和两份查询配置。
      只有基准与处理都真实运行完成后才展示提升幅度。
    </p>

    <table v-if="experiments.length">
      <thead>
        <tr>
          <th>名称</th><th>判断集</th><th>索引</th>
          <th>基准运行</th><th>处理运行</th><th>NDCG@10 Δ</th><th>MRR@10 Δ</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in experiments" :key="e.id" class="clickable"
            @click="$router.push(`/experiments/${e.id}`)">
          <td>{{ e.name }}</td>
          <td>{{ e.judgment_set }}</td>
          <td class="mono">{{ e.index_name }}</td>
          <td><RunBadge :run="e.baseline" /></td>
          <td><RunBadge :run="e.treatment" /></td>
          <td><Delta :value="delta(e, 'ndcg')" /></td>
          <td><Delta :value="delta(e, 'mrr')" /></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="muted">暂无实验。</p>

    <h3>新建实验</h3>
    <form class="create" @submit.prevent="create">
      <input v-model="form.name" placeholder="实验名称" required />
      <select v-model="form.judgment_set_id" required>
        <option disabled value="">选择判断集（名称@版本）</option>
        <option v-for="s in judgmentSets" :key="s.id" :value="s.id">
          {{ s.name }}@{{ s.version }}（{{ s.num_judgments }} 条判断）
        </option>
      </select>
      <input v-model="form.index_name" placeholder="OpenSearch 索引名" required />
      <label class="muted">基准查询配置（JSON）</label>
      <textarea v-model="form.baseline" rows="2" required></textarea>
      <label class="muted">处理查询配置（JSON）</label>
      <textarea v-model="form.treatment" rows="2" required></textarea>
      <div>
        <button type="submit">创建</button>
        <span v-if="error" class="delta-neg"> {{ error }}</span>
      </div>
    </form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import RunBadge from '../components/RunBadge.vue'
import Delta from '../components/Delta.vue'

const experiments = ref([])
const judgmentSets = ref([])
const error = ref('')
const form = reactive({
  name: '',
  judgment_set_id: '',
  index_name: 'docs',
  baseline: JSON.stringify({ type: 'match', field: 'text' }),
  treatment: JSON.stringify({ type: 'multi_match', fields: ['title^3', 'text'], tie_breaker: 0.3 }),
})

function delta(exp, metric) {
  const b = exp.baseline?.metrics?.[metric]
  const t = exp.treatment?.metrics?.[metric]
  return b == null || t == null ? null : t - b
}

async function load() {
  experiments.value = await api.experiments()
  judgmentSets.value = await api.judgmentSets()
}

async function create() {
  error.value = ''
  try {
    const exp = await api.createExperiment({
      name: form.name,
      judgment_set_id: form.judgment_set_id,
      index_name: form.index_name,
      baseline_config: JSON.parse(form.baseline),
      treatment_config: JSON.parse(form.treatment),
    })
    await load()
    form.name = ''
    void exp
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>
