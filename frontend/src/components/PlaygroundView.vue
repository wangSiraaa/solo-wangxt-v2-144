<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'
import { gradeBadge } from '../format.js'

const configs = ref([])
const configId = ref('rc-baseline-body')
const query = ref('docker network debugging')
const size = ref(15)
const result = ref(null)
const error = ref('')
const loading = ref(false)

async function run() {
  loading.value = true; error.value = ''
  try {
    result.value = await api.search({
      query: query.value, config_id: configId.value, size: size.value,
    })
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  configs.value = await api.runConfigs()
  run()
})
</script>

<template>
  <div class="panel">
    <h2>即时检索（可复现）</h2>
    <p class="small muted">
      直接对本地 OpenSearch 索引 <code>ir-corpus-v1</code> 执行检索。所有请求固定
      <code>_score 降序、_id 升序</code> 打破并列，单分片，因此同样输入始终得到同样排名。
    </p>
    <div class="filters">
      <select v-model="configId">
        <option v-for="c in configs" :key="c.config_id" :value="c.config_id">
          {{ c.name }}
        </option>
      </select>
      <input v-model="query" type="text" style="flex:1;min-width:260px"
             placeholder="输入查询，例如 python sort stability timsort"
             @keyup.enter="run" />
      <input v-model.number="size" type="number" min="1" max="100" style="width:80px" title="返回条数" />
      <button class="active" @click="run" :disabled="loading">{{ loading ? '检索中…' : '检索' }}</button>
    </div>
    <div class="small muted" v-if="result">
      命中文档数（引擎口径）{{ result.total_hits }} · 运行配置
      <code>{{ JSON.stringify(result.run_config) }}</code>
    </div>
    <div v-if="error" class="notice">{{ error }}</div>

    <table v-if="result" style="margin-top:10px">
      <thead><tr><th style="width:40px">#</th><th>文档</th><th>正文片段</th><th class="num">BM25</th></tr></thead>
      <tbody>
        <tr v-for="h in result.hits" :key="h.doc_id">
          <td>{{ h.rank }}</td>
          <td>
            <div class="doc-title">{{ h.title }}</div>
            <div class="muted small"><code>{{ h.doc_id }}</code> · {{ h.canonical_doc_id }}</div>
            <div style="margin-top:3px">
              <span v-if="h.tied" class="badge tie">并列分值</span>
              <span v-for="t in h.tags" :key="t" class="badge tag">{{ t }}</span>
            </div>
          </td>
          <td class="small muted">{{ h.body }}</td>
          <td class="num">{{ h.score.toFixed(3) }}</td>
        </tr>
        <tr v-if="!result.hits.length"><td colspan="4" class="muted">无命中（空结果）。</td></tr>
      </tbody>
    </table>
  </div>
</template>
