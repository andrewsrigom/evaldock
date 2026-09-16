<script setup lang="ts">
import { ref, watch, useId, computed } from 'vue'
import { Braces, Check, AlertCircle } from '@lucide/vue'
import { pretty } from '@/api/client'
const props = withDefaults(defineProps<{ modelValue: unknown; label: string; hint?: string; rows?: number; objectOnly?: boolean }>(), { rows: 6 })
const emit = defineEmits<{ 'update:modelValue': [value: any]; validity: [valid: boolean]; dirty: [] }>()
const id = useId(), text = ref(pretty(props.modelValue)), error = ref('')
let last = pretty(props.modelValue)
watch(() => props.modelValue, value => {
  const next = pretty(value)
  if (next !== last) { text.value = next; last = next; error.value = ''; emit('validity', true) }
}, { deep: true })
const lines = computed(() => text.value.split('\n').length)
function change(value: string) {
  text.value = value; emit('dirty')
  try {
    const parsed = JSON.parse(value)
    if (props.objectOnly && (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))) throw new Error('Use a JSON object: { "key": "value" }.')
    error.value = ''; last = pretty(parsed); emit('update:modelValue', parsed); emit('validity', true)
  } catch (e) { error.value = (e as Error).message; emit('validity', false) }
}
function format() { if (!error.value) text.value = pretty(JSON.parse(text.value)) }
</script>
<template>
  <div class="json-field" :class="{ invalid: error }">
    <div class="field-heading"><label :for="id">{{ label }}</label><button type="button" class="text-link" :disabled="!!error" @click="format"><Braces :size="13"/>Format JSON</button></div>
    <p v-if="hint" :id="`${id}-hint`" class="field-hint">{{ hint }}</p>
    <textarea :id="id" :value="text" @input="change(($event.target as HTMLTextAreaElement).value)" :rows="rows" class="code-editor" spellcheck="false" :aria-invalid="!!error" :aria-describedby="`${id}-status`"/>
    <div :id="`${id}-status`" class="json-status" :class="{ 'field-error': error }" aria-live="polite"><AlertCircle v-if="error" :size="13"/><Check v-else :size="13"/>{{ error || `Valid JSON · ${lines} line${lines === 1 ? '' : 's'}` }}</div>
  </div>
</template>
