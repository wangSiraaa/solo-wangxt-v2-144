<script setup>
import { ref, onMounted } from 'vue'
import ExperimentsView from './components/ExperimentsView.vue'
import QueriesView from './components/QueriesView.vue'
import PolicyView from './components/PolicyView.vue'
import PlaygroundView from './components/PlaygroundView.vue'
import { api } from './api.js'

const tab = ref('experiments')
const health = ref({})

onMounted(async () => {
  try { health.value = await api.policy() } catch (e) { /* policy optional here */ }
})
</script>

<template>
  <div class="app">
    <header class="topbar">
      <h1>IR 排序评测台</h1>
      <span class="sub">本地合成语料 · OpenSearch 可复现检索 · pytrec_eval 指标 · PostgreSQL 判断集</span>
      <nav class="tabs">
        <button :class="{active: tab==='experiments'}" @click="tab='experiments'">实验对比</button>
        <button :class="{active: tab==='queries'}" @click="tab='queries'">查询与标注</button>
        <button :class="{active: tab==='policy'}" @click="tab='policy'">指标口径</button>
        <button :class="{active: tab==='playground'}" @click="tab='playground'">即时检索</button>
      </nav>
    </header>

    <ExperimentsView v-if="tab==='experiments'" />
    <QueriesView v-else-if="tab==='queries'" />
    <PolicyView v-else-if="tab==='policy'" />
    <PlaygroundView v-else-if="tab==='playground'" />
  </div>
</template>
