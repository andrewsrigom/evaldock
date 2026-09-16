<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, Copy, Trash2, Search } from '@lucide/vue'
import { Button } from './ui/button'
import JsonField from './JsonField.vue'
import { splitList } from '@/lib/editor'
import type { Obj } from '@/api/client'
const props = defineProps<{ modelValue: Obj; invalid: boolean }>()
const emit = defineEmits<{ dirty: []; validity: [key: string, valid: boolean] }>()
const selected = ref(0), search = ref('')
const cases = computed<Obj[]>(() => props.modelValue.cases)
const current = computed(() => cases.value[selected.value])
const visible = computed(() => cases.value.map((item, index) => ({ item, index })).filter(({ item }) => `${item.case_id} ${(item.tags || []).join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
function uniqueId(base = 'case') { let n = cases.value.length + 1; while (cases.value.some(c => c.case_id === `${base}-${String(n).padStart(3, '0')}`)) n++; return `${base}-${String(n).padStart(3, '0')}` }
function add(duplicate = false) {
  const value = duplicate && current.value ? structuredClone(JSON.parse(JSON.stringify(current.value))) : { input: {}, tags: [], slices: {} }
  cases.value.push({ ...value, case_id: uniqueId(duplicate ? 'copy' : 'case') }); selected.value = cases.value.length - 1; search.value = ''; emit('dirty')
}
function remove() { if (!window.confirm(`Remove ${current.value?.case_id} from this draft? Saved versions are unchanged.`)) return; cases.value.splice(selected.value, 1); selected.value = Math.max(0, selected.value - 1); emit('dirty') }
function optional(key: string, enabled: boolean) { if (!current.value) return; if (enabled) current.value[key] = null; else { delete current.value[key]; emit('validity', key, true) }; emit('dirty') }
</script>
<template>
  <div class="dataset-designation"><label class="check-label"><input v-model="modelValue.config.held_out" type="checkbox" @change="emit('dirty')"/>Held-out evaluation set</label><p class="field-hint">Keep these cases separate from repeated prompt tuning.</p></div>
  <div class="dataset-editor">
    <aside class="editor-case-list"><div class="editor-list-top"><strong>{{ cases.length }} cases</strong><Button type="button" size="sm" variant="outline" :disabled="invalid" @click="add()"><Plus :size="14"/>Add case</Button></div><div class="search-control"><Search :size="15"/><input v-model="search" aria-label="Find dataset case" placeholder="Find a case or tag…"/></div><div class="editor-case-scroll"><button v-for="{ item, index } in visible" :key="index" type="button" :class="{ selected: selected === index }" :aria-current="selected === index ? 'true' : undefined" :disabled="invalid && index !== selected" @click="selected = index"><strong>{{ item.case_id || 'Untitled case' }}</strong><small>{{ 'expected' in item ? item.expected === null ? 'Reference: explicit null' : 'Reference provided' : 'No reference' }}</small></button><p v-if="!visible.length" class="empty-inline">No matching cases.</p></div></aside>
    <section v-if="current" :key="selected" class="editor-case-form" @input="emit('dirty')" @change="emit('dirty')"><div class="section-intro"><div><h3>Case {{ selected + 1 }} of {{ cases.length }}</h3><p>Only the input is sent to the target.</p></div><div class="inline-actions"><button type="button" class="icon-button" title="Duplicate case" aria-label="Duplicate case" :disabled="invalid" @click="add(true)"><Copy :size="16"/></button><button type="button" class="icon-button danger-text" title="Remove case" aria-label="Remove case" :disabled="invalid || cases.length < 2" @click="remove"><Trash2 :size="16"/></button></div></div>
      <label>Case ID<input v-model="current.case_id" aria-label="Case ID" aria-describedby="case-id-hint" required maxlength="160"/><small id="case-id-hint">Stable across versions, so comparisons can pair the same case.</small></label>
      <JsonField v-model="current.input" label="Target input" hint="Any JSON value. Expected answers and context stay separate." @validity="emit('validity', 'input', $event)" @dirty="emit('dirty')"/>
      <div class="reference-section"><label class="check-label"><input type="checkbox" :checked="'expected' in current" @change="optional('expected', ($event.target as HTMLInputElement).checked)"/>Reference output provided</label><p class="field-hint">Unchecked means missing. Use JSON null to explicitly expect an abstention.</p><JsonField v-if="'expected' in current" v-model="current.expected" label="Expected output" :rows="5" @validity="emit('validity', 'expected', $event)" @dirty="emit('dirty')"/></div>
      <label class="check-label"><input type="checkbox" :checked="'context' in current" @change="optional('context', ($event.target as HTMLInputElement).checked)"/>Include evaluator-only context</label><JsonField v-if="'context' in current" v-model="current.context" label="Evaluator context" :rows="4" @validity="emit('validity', 'context', $event)" @dirty="emit('dirty')"/>
      <div class="form-grid"><label>Tags<input :value="(current.tags || []).join(', ')" @change="current.tags = splitList(($event.target as HTMLInputElement).value)" placeholder="critical, adversarial"/><small>Separate tags with commas.</small></label><label>Acceptance criteria<textarea v-model="current.acceptance_criteria" rows="2" placeholder="What makes this case pass?"/></label></div>
      <details><summary>Slices & reference identifiers</summary><JsonField :model-value="current.slices || {}" @update:model-value="current.slices = $event" label="Slices" hint='Named groups, such as { "language": "pt" }. Values must be strings.' object-only :rows="3" @validity="emit('validity', 'slices', $event)" @dirty="emit('dirty')"/><label>Reference identifiers<input :value="(current.references || []).join(', ')" @change="current.references = splitList(($event.target as HTMLInputElement).value)" placeholder="document-001, passage-02"/></label></details>
    </section>
  </div>
</template>
