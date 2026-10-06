<template>
  <span v-if="value == null" class="muted">—</span>
  <span v-else :class="cls">{{ text }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ value: { type: Number, default: null } })
const cls = computed(() =>
  props.value > 1e-9 ? 'delta-pos' : props.value < -1e-9 ? 'delta-neg' : 'delta-zero')
const text = computed(() =>
  (props.value > 0 ? '+' : '') + props.value.toFixed(4))
</script>
