<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ value: unknown; missing?: boolean; compact?: boolean }>()
const formatted = computed(() => props.missing ? '∅  Missing output' : JSON.stringify(props.value, null, 2) ?? 'Unavailable')
</script>
<template><pre class="json-view" :class="{ compact }" tabindex="0">{{ formatted }}</pre></template>
