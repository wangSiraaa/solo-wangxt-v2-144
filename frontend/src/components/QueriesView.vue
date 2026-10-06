<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'
import { gradeBadge } from '../format.js'

const queries = ref([])
const judges = ref([])
const sets = ref([])
const openQ = ref(null)

onMounted(async () => {
  sets.value = await api.judgmentSets?.().catch(() => []) ?? []
  judges.value = await api.judges()
  queries.value = await api.queries()
  if (queries.value.length) openQ.value = queries.value[0].query_id
})
</script>

<template>
  <div>
    <div class="panel">
      <h2>判断者（与实验版本分离）</h2>
      <p class="small muted">
        判断者是独立实体；标注归属到具体判断者，而实验和运行配置是另一组版本对象。
        一次标注可被多个实验复用，实验重跑不会改变判断者归属。
      </p>
      <table>
        <thead><tr><th>判断者 ID</th><th>姓名</th><th>团队</th></tr></thead>
        <tbody>
          <tr v-for="j in judges" :key="j.judge_id">
            <td><code>{{ j.judge_id }}</code></td>
            <td>{{ j.name }}</td>
            <td>{{ j.team }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>查询与相关性标注</h2>
      <div class="filters">
        <button v-for="q in queries" :key="q.query_id"
                :class="{active: openQ===q.query_id}" @click="openQ=q.query_id">
          {{ q.title }}
        </button>
      </div>

      <div v-for="q in queries" v-show="openQ===q.query_id" :key="q.query_id">
        <div class="query-head">
          <h3 style="margin:0">{{ q.title }}</h3>
          <span class="badge tag">{{ q.scenario }}</span>
        </div>
        <p class="small muted">查询词：<code>{{ q.text }}</code></p>
        <p class="small">{{ q.note }}</p>

        <table v-if="q.qrels.length">
          <thead>
            <tr><th style="width:34px">等级</th><th>规范文档 / 正文</th><th>判断者</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r,i) in q.qrels" :key="i">
              <td><span class="badge" :class="gradeBadge(r.grade).cls">{{ r.grade }} · {{ gradeBadge(r.grade).text }}</span></td>
              <td>
                <div class="small"><code>{{ r.canonical_doc_id }}</code></div>
                <div class="muted small" v-if="r.title">{{ r.title }}</div>
              </td>
              <td class="small">{{ r.judge_name }} <span class="muted">({{ r.judge_id }})</span></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="notice">
          该查询在判断集中没有任何标注行：既没有相关文档、也没有 grade=0 记录。
          NDCG/MRR/Recall 均无定义（<code>null</code>），与“有结果但全不相关”的情形区别对待。
        </div>
      </div>
    </div>
  </div>
</template>
