import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', timeout: 180_000, expect: { timeout: 20_000 }, workers: 1,
  use: { baseURL: process.env.EVALDOCK_URL || 'http://localhost:5188', viewport: { width: 1500, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  reporter: [['list'], ['html', { open: 'never' }]],
})
