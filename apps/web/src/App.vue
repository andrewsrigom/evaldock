<script setup lang="ts">
import { computed, provide, ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { useRoute, useRouter } from 'vue-router'
import { Layers3, LayoutDashboard, Database, Cable, SlidersHorizontal, FlaskConical, GitCompareArrows, ListChecks, ShieldCheck, Settings2, ArrowUpRight, LogOut, Menu, X } from '@lucide/vue'
import { api, post, type Project, type User } from './api/client'
import { Button } from './components/ui/button'
const route = useRoute(), router = useRouter(), cache = useQueryClient()
const mobileOpen = ref(false)
watch(() => route.fullPath, () => mobileOpen.value = false)
watch(mobileOpen, async value => { await nextTick(); if (value) document.querySelector<HTMLElement>('.sidebar a')?.focus(); else document.querySelector<HTMLElement>('.mobile-menu')?.focus() })
function resizeNavigation() { if (innerWidth > 900) mobileOpen.value = false }
window.addEventListener('resize', resizeNavigation)
onBeforeUnmount(() => window.removeEventListener('resize', resizeNavigation))
const me = useQuery({ queryKey: ['me'], queryFn: () => api<User>('/auth/me'), retry: false })
const projects = useQuery({ queryKey: ['projects'], queryFn: () => api<Project[]>('/projects'), enabled: computed(() => !!me.data.value) })
const recordContext = useQuery({ queryKey: computed(() => ['record-context', route.params.experimentId, route.params.executionId]), queryFn: () => api<{project_id: string}>(route.params.executionId ? `/executions/${route.params.executionId}` : `/experiments/${route.params.experimentId}`), enabled: computed(() => !!me.data.value && !!(route.params.executionId || route.params.experimentId)) })
const email = ref('demo@evaldock.local'), password = ref(''), loginError = ref(''), loggingIn = ref(false)
const projectId = computed(() => String(route.params.projectId || recordContext.data.value?.project_id || projects.data.value?.[0]?.id || ''))
const selected = computed(() => projects.data.value?.find(p => p.id === projectId.value))
provide('projectId', projectId)
provide('user', me.data)
const links = [
  { key: 'overview', label: 'Overview', icon: LayoutDashboard }, { key: 'datasets', label: 'Datasets', icon: Database },
  { key: 'targets', label: 'Targets', icon: Cable }, { key: 'evaluators', label: 'Evaluators', icon: SlidersHorizontal },
  { key: 'experiments', label: 'Experiments', icon: FlaskConical }, { key: 'compare', label: 'Compare', icon: GitCompareArrows },
  { key: 'reviews', label: 'Human review', icon: ListChecks }, { key: 'gates', label: 'Release checks', icon: ShieldCheck },
  { key: 'settings', label: 'Settings', icon: Settings2 },
]
const currentPage = computed(() => route.path.includes('/compare') ? 'compare' : route.params.experimentId || route.params.executionId ? 'experiments' : String(route.params.page || 'overview'))
async function login() {
  loggingIn.value = true; loginError.value = ''
  try { await post('/auth/login', { email: email.value, password: password.value }); password.value = ''; await me.refetch() }
  catch (e) { loginError.value = (e as Error).message }
  finally { loggingIn.value = false }
}
async function logout() { await post('/auth/logout'); cache.clear(); window.location.assign('/') }
function chooseProject(event: Event) { router.push(`/projects/${(event.target as HTMLSelectElement).value}/overview`) }
</script>
<template>
  <div v-if="me.isPending.value" class="full-center"><Layers3 :size="36" class="logo-mark"/><p>Opening your workbench…</p></div>
  <main v-else-if="!me.data.value" class="login-shell">
    <section class="login-story"><div class="brand"><Layers3 :size="28"/> EvalDock</div><div><h1>Evaluate changes.</h1><p>Run evaluations and compare results.</p></div></section>
    <section class="login-form"><form @submit.prevent="login"><h2>Sign in</h2><label>Email<input v-model="email" type="email" autocomplete="username" required/></label><label>Password<input v-model="password" type="password" autocomplete="current-password" required placeholder="Your workspace password"/></label><div v-if="loginError" class="error" role="alert">{{ loginError }}</div><Button type="submit" :disabled="loggingIn">{{ loggingIn ? 'Signing in…' : 'Sign in' }} <ArrowUpRight :size="16"/></Button><small>The local demo password is generated in the project's .env file.</small></form></section>
  </main>
  <div v-else class="app-shell"><a class="skip-link" href="#main-content">Skip to main content</a><button v-if="mobileOpen" class="nav-backdrop" aria-label="Close navigation" @click="mobileOpen = false"></button>
    <aside id="main-navigation" class="sidebar" :class="{ 'mobile-open': mobileOpen }" @keydown.esc="mobileOpen = false"><RouterLink to="/" class="brand"><span class="brand-icon"><Layers3 :size="22"/></span>EvalDock</RouterLink><div class="workspace-label">WORKSPACE</div><div class="workspace-switch"><span class="workspace-avatar">{{ me.data.value.workspaces[0]?.name?.[0] || 'W' }}</span><div><strong>{{ me.data.value.workspaces[0]?.name || 'Workspace' }}</strong><small>{{ me.data.value.workspaces[0]?.role || 'Member' }}</small></div></div><div class="project-select"><label for="project-switch">PROJECT</label><select id="project-switch" :title="selected?.name" :value="projectId" @change="chooseProject"><option v-for="p in projects.data.value" :key="p.id" :value="p.id">{{ p.name }}</option></select></div><nav aria-label="Main navigation"><RouterLink v-for="link in links" :key="link.key" :to="`/projects/${projectId}/${link.key}`" :class="{ active: currentPage === link.key }" :aria-current="currentPage === link.key ? 'page' : undefined" :title="link.label"><component :is="link.icon" :size="17"/><span>{{ link.label }}</span></RouterLink></nav><div class="sidebar-bottom"><small v-if="selected?.fixture">Deterministic sample project</small><div class="user-bar"><span class="user-avatar">{{ me.data.value.name[0] }}</span><div><strong>{{ me.data.value.name }}</strong><small>{{ me.data.value.email }}</small></div><button aria-label="Sign out" @click="logout"><LogOut :size="16"/></button></div></div></aside>
    <div class="main-shell" :inert="mobileOpen"><header class="topbar"><button class="mobile-menu icon-button" aria-label="Toggle navigation" :aria-expanded="mobileOpen" aria-controls="main-navigation" @click="mobileOpen = !mobileOpen"><X v-if="mobileOpen" :size="20"/><Menu v-else :size="20"/></button><div><span class="muted">Workspace</span><span class="crumb-divider">/</span><span>{{ selected?.name || 'Projects' }}</span></div><div class="topbar-right"><span class="environment">LOCAL</span></div></header><div v-if="projects.error.value" class="content error" role="alert">Could not load projects. <button class="text-link" @click="projects.refetch()">Try again</button></div><RouterView v-else :key="route.fullPath"/></div>
  </div>
</template>
