<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { Braces, ListChecks, Upload, Save, AlertCircle } from '@lucide/vue'
import { api, post, pretty, type Obj, type Project, type Resource, type Version } from '@/api/client'
import { defaults, validationErrors } from '@/lib/editor'
import { Button } from './ui/button'
import ModalFrame from './ModalFrame.vue'
import DatasetCaseEditor from './DatasetCaseEditor.vue'
import ResourceFields from './ResourceFields.vue'
import JsonField from './JsonField.vue'
import JsonView from './JsonView.vue'
const props = defineProps<{ project: Project; kind: string; resource: Resource | null; readonly?: boolean }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const draft = ref<Obj>(defaults(props.kind)), name = ref(props.resource?.name || ''), selectedVersion = ref(props.resource?.versions[0]?.id || '')
const loading = ref(false), saving = ref(false), error = ref(''), credentials = ref<Obj[]>([]), advanced = ref(false)
const invalid = ref<Record<string, boolean>>({}), touched = ref(false), original = ref(''), sourceVersion = ref<Version>()
const importText = ref(''), preview = ref<Obj>(), importing = ref(false), importError = ref(''), importNotice = ref('')
const snapshot = () => pretty({ name: name.value, content: draft.value })
const dirty = computed(() => touched.value || snapshot() !== original.value)
const jsonInvalid = computed(() => Object.values(invalid.value).some(Boolean))
const errors = computed(() => validationErrors(props.kind, draft.value, props.project))
const hasShape = computed(() => props.kind === 'dataset' ? !!draft.value.config && Array.isArray(draft.value.cases) : props.kind === 'evaluator' ? !!draft.value.config && !!draft.value.definition : props.kind === 'suite' ? Array.isArray(draft.value.evaluator_version_ids) : !!draft.value.request_mapping)
watch(() => draft.value.kind, () => { invalid.value = {} })
function validity(key: string, valid: boolean) { invalid.value[key] = !valid }
function discard() { return !dirty.value || window.confirm('Discard your unsaved changes? Saved versions will stay unchanged.') }
function close() { if (!saving.value && discard()) emit('close') }
function leave(event: BeforeUnloadEvent) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
const guard = () => !saving.value && discard()
onBeforeRouteLeave(guard)
onBeforeRouteUpdate(guard)
onBeforeUnmount(() => window.removeEventListener('beforeunload', leave))
async function loadVersion(id: string) {
  loading.value = true; error.value = ''
  try { const v = await api<Version & { cases: Obj[] }>(`/versions/${id}`); sourceVersion.value = v; selectedVersion.value = id; draft.value = props.kind === 'dataset' ? { config: v.config, cases: v.cases } : v.config; invalid.value = {}; touched.value = false; original.value = snapshot(); preview.value = undefined; importText.value = ''; importNotice.value = '' }
  catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
async function changeVersion(event: Event) { const select = event.target as HTMLSelectElement; if (!discard()) { select.value = selectedVersion.value; return }; await loadVersion(select.value) }
onMounted(async () => { original.value = snapshot(); window.addEventListener('beforeunload', leave); if (selectedVersion.value) await loadVersion(selectedVersion.value); if (!props.readonly && ['target','evaluator'].includes(props.kind)) { try { credentials.value = await api<Obj[]>(`/projects/${props.project.id}/credentials`) } catch (e) { error.value = (e as Error).message } } })
async function previewImport() { importing.value = true; importError.value = ''; preview.value = undefined; try { preview.value = await post<Obj>('/datasets/preview', { content: importText.value }) } catch (e) { importError.value = (e as Error).message } finally { importing.value = false } }
function applyImport() { if (!preview.value?.valid) return; draft.value.cases = preview.value.cases; touched.value = true; invalid.value = {}; importNotice.value = `${preview.value.count} cases imported into this draft. Save to create a version.`; preview.value = undefined; importText.value = '' }
async function upload(event: Event) { const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return; if (file.size > 10_000_000) { importError.value = 'Choose a JSONL file smaller than 10 MB.'; return }; importText.value = await file.text(); preview.value = undefined; await previewImport() }
async function save() {
  if (jsonInvalid.value || errors.value.length || !name.value.trim() || saving.value) return
  saving.value = true; error.value = ''
  try { const payload = props.kind === 'dataset' ? draft.value : { config: draft.value }; if (props.resource) await post(`/resources/${props.resource.id}/versions`, payload); else await post(`/projects/${props.project.id}/resources`, { kind: props.kind, name: name.value.trim(), ...payload }); touched.value = false; original.value = snapshot(); emit('saved') }
  catch (e) { error.value = (e as Error).message }
  finally { saving.value = false }
}
</script>
<template>
  <ModalFrame :title="resource ? `${readonly ? 'Inspect' : 'Edit'} ${resource.name}` : `New ${kind}`" subtitle="Saved versions are immutable. Changes are saved as a new version." wide :busy="saving" @close="close">
    <div v-if="loading" class="empty-state" role="status">Loading version…</div>
    <form v-else @submit.prevent="save"><div class="modal-body"><div v-if="error" class="error" role="alert">{{ error }}</div><div class="form-grid editor-metadata"><label>Name<input v-model="name" :disabled="!!resource || readonly" required maxlength="160" placeholder="A descriptive name"/></label><label v-if="resource">Inspect version<select :value="selectedVersion" @change="changeVersion"><option v-for="v in resource.versions" :key="v.id" :value="v.id">v{{ v.number }} · {{ new Date(v.created_at).toLocaleString() }}</option></select><small class="mono">{{ sourceVersion?.fingerprint.slice(0, 16) }}</small></label></div>
      <div class="editor-mode"><div class="segmented-control" aria-label="Editor mode"><button type="button" :class="{ active: !advanced }" :disabled="jsonInvalid || !hasShape" @click="advanced = false"><ListChecks :size="15"/>Guided editor</button><button type="button" :class="{ active: advanced }" :disabled="jsonInvalid" @click="advanced = true"><Braces :size="15"/>Advanced JSON</button></div><span class="draft-indicator">{{ readonly ? 'Read-only access' : dirty ? 'Unsaved changes' : resource ? `Based on v${sourceVersion?.number || ''}` : 'New draft' }}</span></div>
      <fieldset :disabled="readonly || saving" class="editor-fields">
        <details v-if="kind === 'dataset' && !readonly" class="import-section"><summary><Upload :size="15"/>Import JSONL with line-by-line validation</summary><p class="field-hint">Validate a file or pasted lines, then replace the cases in this draft.</p><label>Choose JSONL file<input type="file" accept=".jsonl,.ndjson,.txt,application/x-ndjson" @change="upload"/></label><label>JSONL content<textarea v-model="importText" class="code-editor" rows="5" @input="preview = undefined"/></label><Button type="button" variant="outline" :disabled="!importText.trim() || importing" @click="previewImport">{{ importing ? 'Validating…' : 'Validate & preview' }}</Button><div v-if="importError" class="error" role="alert">{{ importError }}</div><template v-if="preview"><div class="import-result" :class="preview.valid ? 'notice' : 'error'"><strong>{{ preview.valid ? `${preview.count} valid cases` : 'Import needs corrections' }}</strong></div><ul v-if="preview.errors.length" class="validation-list"><li v-for="(e, i) in preview.errors" :key="i">Line {{ e.line }}: {{ e.message }}</li></ul><JsonView :value="{ count: preview.count, errors: preview.errors, preview: preview.preview.slice(0,2) }" compact/><Button v-if="preview.valid" type="button" @click="applyImport">Use {{ preview.count }} imported cases</Button></template></details>
        <div v-if="importNotice" class="notice" role="status">{{ importNotice }}</div>
        <JsonField v-if="advanced" :model-value="draft" @update:model-value="draft = $event" label="Version content" :rows="20" object-only @validity="validity('advanced', $event)" @dirty="touched = true"/>
        <DatasetCaseEditor v-else-if="kind === 'dataset' && hasShape" :key="selectedVersion + importNotice" v-model="draft" :invalid="jsonInvalid" @dirty="touched = true" @validity="validity"/>
        <ResourceFields v-else-if="hasShape" :key="draft.kind" :kind="kind" v-model="draft" :project="project" :credentials="credentials" @dirty="touched = true" @validity="validity"/>
        <div v-else class="error">The draft structure needs correction. Open Advanced JSON to inspect it.</div>
      </fieldset>
      <div v-if="!readonly && (jsonInvalid || errors.length)" class="validation-summary" aria-live="polite"><AlertCircle :size="16"/><div><strong>{{ jsonInvalid ? 'Fix the highlighted JSON before continuing.' : 'Complete the required configuration.' }}</strong><ul v-if="errors.length"><li v-for="message in errors.slice(0,5)" :key="message">{{ message }}</li></ul><small v-if="errors.length > 5">And {{ errors.length - 5 }} more issues.</small></div></div>
    </div><footer class="modal-actions"><div><strong>{{ resource ? `Save as v${(resource.versions[0]?.number || 0) + 1}` : 'Create version 1' }}</strong><small>{{ kind === 'dataset' ? `${draft.cases?.length || 0} cases · ` : '' }}Existing experiments keep their pinned versions.</small></div><Button type="button" variant="outline" :disabled="saving" @click="close">{{ readonly ? 'Close' : 'Cancel' }}</Button><Button v-if="!readonly" type="submit" :disabled="saving || (!!resource && !sourceVersion) || jsonInvalid || !!errors.length || !name.trim() || (!!resource && !dirty)"><Save :size="15"/>{{ saving ? 'Saving…' : 'Save immutable version' }}</Button></footer></form>
  </ModalFrame>
</template>
