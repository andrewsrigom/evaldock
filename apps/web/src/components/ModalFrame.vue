<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { X } from '@lucide/vue'
const props = defineProps<{ title: string; subtitle?: string; wide?: boolean; busy?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLElement>(), previous = document.activeElement as HTMLElement | null
function close() { if (!props.busy) emit('close') }
function keyboard(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); close() }
  if (event.key !== 'Tab') return
  const nodes = [...(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, a[href], [tabindex="0"]') || [])].filter(e => e.getClientRects().length)
  const first = nodes[0], last = nodes.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
onMounted(async () => { document.body.style.overflow = 'hidden'; document.addEventListener('keydown', keyboard); await nextTick(); dialog.value?.querySelector<HTMLElement>('input:not(:disabled), button')?.focus(); const app = document.getElementById('app'); if (app) { app.inert = true; app.setAttribute('aria-hidden', 'true') } })
onBeforeUnmount(() => { document.body.style.overflow = ''; const app = document.getElementById('app'); if (app) { app.inert = false; app.removeAttribute('aria-hidden') }; document.removeEventListener('keydown', keyboard); previous?.focus() })
</script>
<template>
  <Teleport to="body"><div class="modal-overlay" @click.self="close"><section ref="dialog" role="dialog" aria-modal="true" :aria-label="title" class="modal" :class="{ 'modal-wide': wide }"><div class="panel-header"><div><h2>{{ title }}</h2><p v-if="subtitle" class="field-hint">{{ subtitle }}</p></div><button type="button" class="icon-button" aria-label="Close dialog" :disabled="busy" @click="close"><X :size="20"/></button></div><slot/></section></div></Teleport>
</template>
