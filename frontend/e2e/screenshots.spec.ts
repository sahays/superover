import { test, expect, Page } from '@playwright/test'

const DIR = './e2e/screenshots'

async function waitForContent(page: Page) {
  await page.waitForLoadState('networkidle')
  await expect(page.locator('main')).toBeVisible()
  await page.waitForTimeout(1000)
}

async function snap(page: Page, name: string) {
  await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: false })
}

/** Navigate to list, click first detail link, return the detail page URL path */
async function getFirstDetailPath(page: Page, listPath: string, urlPattern: RegExp, selector: string) {
  await page.goto(listPath)
  await waitForContent(page)
  await page.waitForTimeout(500)
  await page.locator(selector).first().click()
  await page.waitForURL(urlPattern, { timeout: 10000 })
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(2000)
  return new URL(page.url()).pathname
}

/** Scroll a specific element into view and wait */
async function scrollToElement(page: Page, selector: string) {
  const el = page.locator(selector).first()
  await el.scrollIntoViewIfNeeded()
  await page.waitForTimeout(500)
}

// ── List pages ──────────────────────────────────────────────

const listPages = [
  { name: 'home', path: '/' },
  { name: 'media', path: '/media' },
  { name: 'scene-analysis', path: '/scene-analysis' },
  { name: 'prompts', path: '/prompts' },
  { name: 'search', path: '/search' },
]

for (const pg of listPages) {
  test(`screenshot: ${pg.name}`, async ({ page }) => {
    await page.goto(pg.path)
    await waitForContent(page)
    await snap(page, pg.name)
  })
}

// ── Create pages ────────────────────────────────────────────

test('screenshot: prompts-create', async ({ page }) => {
  await page.goto('/prompts/new')
  await waitForContent(page)
  await snap(page, 'prompts-create')
})

// ── Media Detail ────────────────────────────────────────────

test('screenshot: media-detail', async ({ page }) => {
  await getFirstDetailPath(page, '/media', /\/media\/[^/]/, 'a[href^="/media/"]')
  await snap(page, 'media-detail')
})

// ── Scene Detail ────────────────────────────────────────────

test('screenshot: scene-detail', async ({ page }) => {
  await getFirstDetailPath(page, '/scene-analysis', /\/scene\/[^/]/, 'a[href^="/scene/"]')
  await snap(page, 'scene-detail')
})

// ── Scene Results ───────────────────────────────────────────

test('screenshot: scene-results', async ({ page }) => {
  // Navigate to first scene detail, then to results
  await getFirstDetailPath(page, '/scene-analysis', /\/scene\/[^/]/, 'a[href^="/scene/"]')

  // Click "View Full Results" or results link
  const resultsLink = page.locator('a[href*="/results"]').first()
  if (await resultsLink.isVisible()) {
    await resultsLink.click()
    await page.waitForURL(/\/scene\/[^/]+\/results/, { timeout: 10000 })
    await waitForContent(page)

    // Header with cost bar
    await snap(page, 'scene-results-header')

    // Scroll to chunk content
    const chunkContent = page.locator('pre.whitespace-pre-wrap').first()
    if (await chunkContent.isVisible()) {
      await chunkContent.scrollIntoViewIfNeeded()
      await page.waitForTimeout(500)
      await snap(page, 'scene-results-content')
    }
  }
})

// ── Prompt Detail ───────────────────────────────────────────

test('screenshot: prompts-detail', async ({ page }) => {
  await getFirstDetailPath(page, '/prompts', /\/prompts\/[^/]/, 'a[href^="/prompts/"]')
  await snap(page, 'prompts-detail')
})
