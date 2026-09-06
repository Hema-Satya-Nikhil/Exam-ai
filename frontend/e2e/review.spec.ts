import { expect, test } from '@playwright/test';

/**
 * Composite Review browser E2E — drives the REAL Review UI end to end:
 * FINAL CHECK states, Part A / Part B rendering, OR divider, validation-gated
 * export, regeneration, lock -> locked regen blocked -> unlock -> regen, and
 * reload persistence. Requires a generated composite paper id (see
 * playwright.config.ts header / `npm run e2e:seed`).
 */

const PAPER_ID = process.env.E2E_PAPER_ID || '';
const FACULTY = { email: 'faculty@examcraft.ai', password: 'faculty123' };
const OUT = 'log in through the real login form';

test.skip(!PAPER_ID, 'E2E_PAPER_ID is not set — run `npm run e2e:seed` first.');

// Tokens captured by the form-login test and injected into subsequent tests.
// Each Playwright test gets a fresh browser context, so without this the
// review tests would run unauthenticated and hit "Paper not found".
let authTokens: { access: string | null; refresh: string | null } | null = null;

test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.title.includes(OUT)) return; // the login test authenticates for real
  test.skip(!authTokens, 'auth state unavailable — form-login test must pass first');
  await page.addInitScript(
    ([access, refresh]) => {
      if (access) window.localStorage.setItem('ecai_access_token', access);
      if (refresh) window.localStorage.setItem('ecai_refresh_token', refresh);
    },
    [authTokens?.access ?? null, authTokens?.refresh ?? null] as [string | null, string | null]
  );
});

test.describe.serial('composite Review workflow', () => {
  test.beforeAll(async ({ request }) => {
    // Fail fast with a clear message when the backend is not reachable.
    const health = await request.get('http://localhost:8000/health');
    expect(health.ok(), 'backend must be live on :8000 (see playwright.config.ts)').toBeTruthy();
  });

  test('faculty can log in through the real login form', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', FACULTY.email);
    await page.fill('input[type="password"]', FACULTY.password);
    await Promise.all([
      page.waitForURL(/dashboard|login/, { timeout: 30000 }),
      page.click('button[type="submit"]'),
    ]);
    await page.waitForTimeout(1500);
    const authed = await page.evaluate(() =>
      Boolean(window.localStorage.getItem('ecai_access_token')));
    expect(authed).toBe(true);

    // Share the session with subsequent tests (fresh context per test).
    authTokens = await page.evaluate(() => ({
      access: localStorage.getItem('ecai_access_token'),
      refresh: localStorage.getItem('ecai_refresh_token')
    }));
  });

  test('FINAL CHECK renders the passed state from the persisted validation', async ({ page }) => {
    await page.goto(`/review?paper_id=${PAPER_ID}`);
    await page.waitForSelector('[data-testid="final-check-list"]');
    await page.waitForSelector('[data-testid="question-card"]');

    await expect(page.locator('[data-testid="final-check-passed"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="final-check-blocked"]')).toHaveCount(0);
  });

  test('Review renders Part A, Part B and the OR alternative', async ({ page }) => {
    await page.goto(`/review?paper_id=${PAPER_ID}`);
    await page.waitForSelector('[data-testid="question-card"]');

    const banners = await page.locator('[data-testid="part-banner"]').allTextContents();
    expect(banners.some((b) => /PART A/i.test(b) && /20 Minutes/i.test(b))).toBe(true);
    expect(banners.some((b) => /PART B/i.test(b) && /90 Minutes/i.test(b))).toBe(true);

    await expect(
      page.locator('[data-testid="part-a-section"] [data-testid="question-card"]'),
    ).toHaveCount(10);
    await expect(page.locator('[data-testid="question-card"]')).toHaveCount(14);
    await expect(page.locator('[data-testid="or-divider"]').first()).toBeVisible();
    await expect(page.locator('[data-testid="or-alternative"]').first()).toBeVisible();

    const texts = await page.locator('[data-testid="question-text"]').allTextContents();
    const dirty = texts.filter((t) =>
      /^\s*(question\s*\d+|\d+[.)]\s|unit\b|topic\s*:|marks?\s*:|bloom\b)/i.test(t || ''));
    expect(dirty, `metadata leaked into question text: ${dirty.slice(0, 2)}`).toHaveLength(0);
  });

  test('export is enabled and PDF downloads without any approval step', async ({ page }) => {
    await page.goto(`/review?paper_id=${PAPER_ID}`);
    await page.waitForSelector('[data-testid="question-card"]');

    const pdfBtn = page.getByRole('button', { name: /pdf/i });
    const docxBtn = page.getByRole('button', { name: /docx/i });
    await expect(pdfBtn).toBeEnabled();
    await expect(docxBtn).toBeEnabled();

    const downloadPromise = page.waitForEvent('download', { timeout: 60000 });
    await pdfBtn.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename() || '').toMatch(/\.pdf$/i);
  });

  test('Part A question can be regenerated from the UI', async ({ page }) => {
    await page.goto(`/review?paper_id=${PAPER_ID}`);
    await page.waitForSelector('[data-testid="question-card"]');

    const card = page
      .locator('[data-testid="part-a-section"] [data-testid="question-card"]')
      .first();
    await card.locator('input').fill('make it application-oriented');
    await card.getByRole('button', { name: /regenerate/i }).click();
    await page.waitForSelector('text=/regenerated/i', { timeout: 120000 });
  });

  test('lock blocks regeneration, unlock re-enables it', async ({ page }) => {
    await page.goto(`/review?paper_id=${PAPER_ID}`);
    await page.waitForSelector('[data-testid="question-card"]');

    const card = page
      .locator('[data-testid="part-a-section"] [data-testid="question-card"]')
      .nth(2);
    await card.getByRole('button', { name: /lock/i }).click();
    await page.waitForSelector('[data-testid="lock-state"]', { timeout: 30000 });

    const lockedCard = page
      .locator('[data-testid="part-a-section"] [data-testid="question-card"]')
      .filter({ has: page.locator('[data-testid="lock-state"]') })
      .first();
    await expect(lockedCard.getByRole('button', { name: /regenerate/i })).toBeDisabled();

    await lockedCard.getByRole('button', { name: /unlock/i }).click();
    await page.waitForSelector('[data-testid="lock-state"]', { state: 'detached', timeout: 30000 });

    const regenBtn = page
      .locator('[data-testid="part-a-section"] [data-testid="question-card"]')
      .nth(2)
      .getByRole('button', { name: /regenerate/i });
    await expect(regenBtn).toBeEnabled();
    await regenBtn.click();
    await page.waitForSelector('text=/regenerated/i', { timeout: 120000 });
  });

  test('state persists across a page reload', async ({ page }) => {
    await page.goto(`/review?paper_id=${PAPER_ID}`);
    await page.waitForSelector('[data-testid="question-card"]');
    await page.reload();
    await page.waitForSelector('[data-testid="question-card"]');
    await expect(page.locator('[data-testid="question-card"]')).toHaveCount(14);
  });
});
