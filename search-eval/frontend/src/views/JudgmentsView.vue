<template>
  <div>
    <h2>判断集</h2>
    <p class="muted">判断集按版本冻结；每条判断都记录判断者，与实验配置完全分离。</p>

    <table v-if="sets.length">
      <thead>
        <tr><th>名称</th><th>版本</th><th>判断数</th><th>判断者</th><th>创建时间</th></tr>
      </thead>
      <tbody>
        <tr v-for="s in sets" :key="s.id" class="clickable" @click="select(s.id)">
          <td>{{ s.name }}</td>
          <td>{{ s.version }}</td>
          <td>{{ s.num_judgments }}</td>
          <td>{{ s.judges.join(', ') }}</td>
          <td class="muted">{{ new Date(s.created_at).toLocaleString() }}</td>
        </tr>
      </tbody>
    </table>

    <div v-if="detail">
      <h3>{{ detail.name }}@{{ detail.version }}</h3>
      <p class="muted">{{ detail.description }}</p>
      <div v-for="q in detail.queries" :key="q.query_id" class="qblock">
        <h4>
          {{ q.text }} <span class="muted mono">({{ q.query_id }})</span>
          <span v-if="q.num_rel === 0" class="tag">零相关</span>
          <span v-else class="tag">{{ q.num_rel }} 个相关文档</span>
        </h4>
        <table>
          <thead><tr><th>文档</th><th>等级</th><th>判断者</th></tr></thead>
          <tbody>
            <tr v-for="j in q.judgments" :key="j.doc_id">
              <td class="mono">{{ j.doc_id }}</td>
              <td><GradeBadge :grade="j.grade" /></td>
              <td>{{ j.judge }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import GradeBadge from '../components/GradeBadge.vue'

const sets = ref([])
const detail = ref(null)

async function select(id) {
  detail.value = await api.judgmentSet(id)
}

onMounted(async () => {
  sets.value = await api.judgmentSets()
  if (sets.value.length) await select(sets.value[0].id)
})
</script>

<style scoped>
.qblock { margin-bottom: 22px; }
.qblock h4 { margin-bottom: 6px; }
</style>
