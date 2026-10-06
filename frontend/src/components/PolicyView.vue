<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'

const policy = ref(null)
onMounted(async () => { policy.value = await api.policy() })
</script>

<template>
  <div v-if="policy">
    <div class="panel">
      <h2>评测口径（分母、截断、未标注、重复、并列）</h2>
      <p class="small muted">
        以下定义由后端 <code>pytrec_eval</code>（trec_eval 9.0 绑定）实际执行，前端仅展示同一份配置，
        保证“写出来的口径”与“算出来的数字”一致。
      </p>
      <div class="policy-grid">
        <div class="policy-item" v-for="m in policy.metrics" :key="m.key">
          <h3 style="margin:0 0 4px">{{ m.display }} <span class="muted small">({{ m.key }})</span></h3>
          <dl>
            <dt>分子</dt><dd class="small">{{ m.numerator }}</dd>
            <dt>分母</dt><dd class="small">{{ m.denominator }}</dd>
            <dt>取值范围</dt><dd class="small">{{ m.range }}</dd>
            <dt>截断位置</dt><dd class="small">@{{ m.cutoff }}</dd>
            <dt>未标注文档策略</dt><dd class="small">{{ m.unjudged }}</dd>
            <dt>零相关查询</dt><dd class="small">{{ m.empty_query }}</dd>
            <dt>重复文档</dt><dd class="small">{{ m.duplicates }}</dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="panel">
      <h2>汇总与边界规则</h2>
      <dl class="policy-item">
        <dt>宏平均</dt><dd class="small">{{ policy.aggregation }}</dd>
        <dt>并列分值</dt><dd class="small">{{ policy.tie_breaking }}</dd>
        <dt>去重单位</dt><dd class="small">{{ policy.dedup }}</dd>
        <dt>相关阈值</dt><dd class="small">grade ≥ {{ policy.rel_threshold }} 视为二值相关（MRR / Recall）。
          等级：
          <span v-for="(label,g) in policy.grade_labels" :key="g">
            {{ g }}={{ label }}
          </span>
        </dd>
      </dl>
    </div>
  </div>
</template>
