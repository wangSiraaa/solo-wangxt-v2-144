<template>
  <span v-if="grade == null" class="grade unjudged" title="未标注，按 0 级处理">未标注</span>
  <span v-else class="grade" :class="`g${grade}`">{{ grade }}</span>
</template>

<script setup>
defineProps({ grade: { type: Number, default: null } })
</script>
