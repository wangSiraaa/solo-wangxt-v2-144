<template>
  <span v-if="value === 'new'" class="delta-pos">新增</span>
  <span v-else-if="value === 'dropped'" class="delta-neg">掉出</span>
  <span v-else-if="typeof value === 'number' && value < 0" class="delta-pos">↑{{ -value }}</span>
  <span v-else-if="typeof value === 'number' && value > 0" class="delta-neg">↓{{ value }}</span>
  <span v-else class="muted">—</span>
</template>

<script setup>
defineProps({ value: { type: [Number, String], default: null } })
</script>
