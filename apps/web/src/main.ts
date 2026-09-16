import { createApp } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Workbench from './pages/Workbench.vue'
import Compare from './pages/Compare.vue'
import './style.css'
import './catalogforge.css'

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', component: Workbench },
  { path: '/projects/:projectId/compare', component: Compare },
  { path: '/projects/:projectId/:page?', component: Workbench },
  { path: '/experiments/:experimentId', component: Workbench },
  { path: '/cases/:executionId', component: Workbench },
] })
createApp(App).use(router).use(VueQueryPlugin, { queryClientConfig: { defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } } }).mount('#app')
