<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { pretty, type Obj } from '@/api/client'
import JsonField from './JsonField.vue'
const props = defineProps<{ modelValue: string; cases: Obj[]; repetitions: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; validity: [valid: boolean] }>()
const value = ref<unknown>(JSON.parse(props.modelValue)), jsonValid = ref(true), fileError = ref('')
const errors = computed(() => {
  if (!Array.isArray(value.value)) return ['Use a JSON array of output records.']
  const ids = new Set(props.cases.map(c => c.case_id)), seen = new Set<string>(), issues: string[] = []
  value.value.forEach((r, i) => {
    if (!r || typeof r !== 'object' || !('output' in r)) { issues.push(`Record ${i + 1}: case_id and output are required. An explicit null output is allowed.`); return }
    const key = `${r.case_id}:${r.replicate ?? 0}`
    if (!ids.has(r.case_id)) issues.push(`Record ${i + 1}: unknown case ID ${r.case_id}.`)
    if (!Number.isInteger(r.replicate ?? 0) || (r.replicate ?? 0) < 0 || (r.replicate ?? 0) >= props.repetitions) issues.push(`Record ${i + 1}: replicate must be between 0 and ${props.repetitions - 1}.`)
    if (seen.has(key)) issues.push(`Duplicate output: ${key}.`)
    seen.add(key)
  })
  return issues
})
const total = computed(() => props.cases.length * props.repetitions)
const count = computed(() => Array.isArray(value.value) ? value.value.length : 0)
watch([jsonValid, errors], () => emit('validity', jsonValid.value && !errors.value.length), { immediate: true })
function update(v: unknown) { value.value = v; emit('update:modelValue', pretty(v)) }
async function upload(event: Event) { const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return; try { if (file.size > 10_000_000) throw new Error('Choose a file smaller than 10 MB.'); update(JSON.parse(await file.text())); jsonValid.value = true; fileError.value = '' } catch (e) { fileError.value = (e as Error).message } }
</script>
<template>
  <label>Import outputs file<input type="file" accept=".json,application/json" @change="upload"/><small>JSON array: case_id, replicate (default 0), output, and optional trace.</small></label><div v-if="fileError" class="error" role="alert">{{ fileError }}</div>
  <JsonField :model-value="value" @update:model-value="update" label="Imported outputs" hint='Example: [{ "case_id": "case-001", "replicate": 0, "output": null }]' :rows="8" @validity="jsonValid = $event"/>
  <div v-if="errors.length" class="error"><ul class="validation-list"><li v-for="e in errors.slice(0,5)" :key="e">{{ e }}</li></ul></div>
  <div v-else class="info-strip">{{ count }} / {{ total }} outputs supplied. {{ total - count > 0 ? `${total - count} missing outputs will remain visible as missing coverage.` : 'All planned case / replicate pairs are covered.' }} No target requests are made.</div>
</template>
