<script setup lang="ts">
import { computed } from 'vue'
import type { Result } from '@/api/client'
import { criteriaSummary, metricLabel } from '@/lib/presentation'
const props = defineProps<{ results: Result[]; expected?: number }>()
const summary = computed(() => criteriaSummary(props.results, props.expected))
const issues = computed(() => props.results.filter(r => r.status !== 'scored' || r.passed === false))
</script>
<template>
  <div class="criteria-summary">
    <strong :class="summary.failed ? 'red-text' : summary.passed === summary.total && summary.total ? 'green-text' : ''">{{ summary.passed || summary.failed ? `${summary.passed}/${summary.total} passed` : `${summary.scored}/${summary.total} scored` }}</strong>
    <small v-if="summary.unscored">{{ summary.unscored }} unscored</small>
    <small v-if="summary.noDecision">{{ summary.noDecision }} without pass/fail</small>
    <small v-for="result in issues" :key="result.metric_key" :class="result.passed === false ? 'red-text' : ''">{{ metricLabel(result.metric_key) }} · {{ result.status === 'scored' ? 'failed' : result.status.replaceAll('_', ' ') }}</small>
  </div>
</template>
