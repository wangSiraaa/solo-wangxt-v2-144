<template>
  <span v-if="!run" class="badge missing">未运行</span>
  <span v-else-if="run.status === 'completed'" class="badge ok">已完成</span>
  <span v-else-if="run.status === 'failed'" class="badge missing">失败</span>
  <span v-else class="badge pending">{{ run.status }}</span>
</template>

<script setup>
defineProps({ run: { type: Object, default: null } })
</script>
