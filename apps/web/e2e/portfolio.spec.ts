import { test, expect, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('../..')
const env = Object.fromEntries(fs.readFileSync(path.join(root, '.env'), 'utf8').split('\n').filter(l => l.includes('=')).map(l => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]))
const read = (name: string) => fs.existsSync(path.join(root, name)) ? JSON.parse(fs.readFileSync(path.join(root, name), 'utf8')) : null
const setup = read('docs/ai-setup.json')
const evidence = read('docs/catalog-public-v1.json')
const calibration = read('docs/catalog-ai-v2/summary.json')
const shots = path.join(root, 'docs/portfolio')

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill('demo@evaldock.local')
  await page.getByLabel('Password', { exact: true }).fill(env.DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Project overview', exact: true })).toBeVisible()
}

test('report, comparison and release checks form a clear read-only journey', async ({ page }) => {
  test.skip(!setup || !evidence || !calibration, 'Load the calibrated catalog pilot first')
  const errors: string[] = [], mutations: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await login(page)
  // Block unexpected writes, including target tests and model calls, during this review.
  await page.route('**/api/**', async route => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) {
      mutations.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`)
      await route.abort()
    } else await route.continue()
  })
  fs.mkdirSync(shots, { recursive: true })
  const base = `/projects/${setup.project_id}`
  const validation = calibration.runs.validation.id
  await page.goto(`${base}/compare?candidate=${validation}`)
  await expect(page.getByLabel('Baseline experiment', { exact: true })).toHaveValue(evidence.runs.validation.baseline_id)
  await expect(page.getByRole('tab', { name: 'All cases 4', exact: true })).toBeVisible()
  await expect(page.getByLabel('Comparison metric')).toHaveValue('field_accuracy')
  expect(await page.getByLabel('Comparison metric').locator('option').allTextContents()).not.toContain('Source support')
  await page.getByLabel('Comparison metric').selectOption('record_exact')
  await expect(page.getByRole('tab', { name: 'Improvements 2', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Improvements 2', exact: true }).click()
  await expect(page.locator('.reference-grid')).not.toBeVisible()
  await page.screenshot({ path: path.join(shots, 'comparison-desktop.png'), fullPage: false })
  await page.getByRole('button', { name: 'Reference & source context', exact: true }).click()
  await expect(page.locator('.reference-grid')).toContainText('source_url')
  await page.getByRole('link', { name: 'Open case', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Source context', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Telemetry & provenance', exact: true })).not.toBeVisible()
  await page.getByText('Execution details', { exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Telemetry & provenance', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Back to experiment', exact: false }).click()
  await expect(page.getByRole('heading', { name: 'OpenAI validation v2', exact: true })).toBeVisible()
  await expect(page.locator('.criteria-summary')).toHaveCount(4)
  await expect(page.locator('.criteria-summary').first()).toHaveText('7/7 passed')
  await expect(page.getByRole('button', { name: 'Rescore outputs', exact: true })).not.toBeVisible()
  await page.screenshot({ path: path.join(shots, 'results-desktop.png'), fullPage: false })
  await page.getByLabel('Filter case results').selectOption('failing')
  await expect(page.getByRole('heading', { name: 'No cases match this filter', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Show all cases', exact: true }).click()
  await expect(page.locator('.criteria-summary')).toHaveCount(4)
  await page.getByRole('main').getByRole('link', { name: 'Release checks', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Checks passed', exact: true })).toBeVisible()
  await expect(page.getByLabel('Experiment', { exact: true })).toHaveValue(validation)
  await expect(page.getByRole('button', { name: 'Save gate policy', exact: true })).not.toBeVisible()
  await page.screenshot({ path: path.join(shots, 'release-checks-desktop.png'), fullPage: false })
  await page.getByLabel('Experiment', { exact: true }).selectOption(calibration.runs.controls.id)
  await expect(page.getByRole('heading', { name: 'Changes needed', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Checks passed', exact: true })).not.toBeVisible()
  await page.getByLabel('Experiment', { exact: true }).selectOption(evidence.runs.validation.baseline_id)
  await expect(page.getByRole('heading', { name: 'Unable to verify', exact: true })).toBeVisible()
  await expect(page.getByText('This run has no pinned baseline. Choose a candidate run with a baseline.', { exact: true })).toBeVisible()
  await page.getByLabel('Experiment', { exact: true }).selectOption(validation)
  await expect(page.getByRole('heading', { name: 'Checks passed', exact: true })).toBeVisible()
  await page.getByText('Edit release policy', { exact: true }).click()
  const regressions = page.getByLabel('Maximum regressions', { exact: true })
  const original = await regressions.inputValue()
  await regressions.fill('2')
  page.once('dialog', async dialog => { expect(dialog.message()).toContain('without saving'); await dialog.dismiss() })
  await page.getByRole('link', { name: 'Overview', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Release checks', exact: true })).toBeVisible()
  await regressions.fill(original)
  await page.getByRole('link', { name: 'Overview', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Project overview', exact: true })).toBeVisible()
  await page.screenshot({ path: path.join(shots, 'overview-desktop.png'), fullPage: false })
  expect(errors).toEqual([])
  expect(mutations).toEqual([])
})

test('mobile navigation and editing stay usable without page overflow', async ({ page }) => {
  test.skip(!setup || !calibration, 'Load the calibrated catalog pilot first')
  await login(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const base = `/projects/${setup.project_id}`
  const urls = [`${base}/overview`, `${base}/compare`, `${base}/gates`, `/experiments/${calibration.runs.validation.id}`, `${base}/datasets`, `${base}/settings`]
  for (const url of urls) {
    await page.goto(url)
    await expect(page.locator('h1')).toBeVisible()
    await expect(page.getByText('Loading your project…', { exact: true })).not.toBeVisible()
    if (url.endsWith('/compare')) {
      await expect(page.getByRole('tab', { name: 'All cases 4', exact: true })).toBeVisible()
      await expect.poll(() => page.locator('.evidence-header').evaluate(e => e.scrollWidth <= e.clientWidth)).toBe(true)
    }
    if (url.endsWith('/gates')) await expect(page.getByRole('heading', { name: 'Checks passed', exact: true })).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), { message: `Page overflow at ${url}` }).toBe(true)
    if (url.endsWith('/overview') || url.endsWith('/gates')) {
      fs.mkdirSync(shots, { recursive: true })
      await page.screenshot({ path: path.join(shots, `${url.endsWith('/gates') ? 'release-checks' : 'overview'}-mobile.png`), fullPage: true })
    }
  }
  await page.getByRole('button', { name: 'Toggle navigation', exact: true }).click()
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible()
  await page.getByRole('link', { name: 'Datasets', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Toggle navigation', exact: true })).toHaveAttribute('aria-expanded', 'false')
  await page.getByRole('button', { name: 'New dataset', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(page.locator('#app')).toHaveAttribute('inert', '')
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'New dataset', exact: true })).toBeFocused()
})
