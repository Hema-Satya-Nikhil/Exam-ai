import { test, expect } from '@playwright/test';

/**
 * Landing page smoke checks — public (unauthenticated) route.
 * Verifies the redesigned hero, CTAs, value cards, and example-structure
 * highlight render in a real browser.
 */
test.describe('Landing page', () => {
  test('hero renders with primary CTA to the create flow', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: /create better question papers with ai/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /create question paper/i }).first()).toHaveAttribute('href', '/create');
  });

  test('value cards and how-it-works sections are present', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /how it works/i })).toBeVisible();
    await expect(page.getByText('Upload syllabus')).toBeVisible();
    await expect(page.getByText('Reviewable')).toBeVisible();
  });

  test('example exam structure is labelled as illustrative', async ({ page }) => {
    await page.goto('/');
    const aside = page.getByRole('complementary', { name: /example exam structure/i });
    await expect(aside).toBeVisible();
    await expect(page.getByText(/illustrative example/i)).toBeVisible();
  });

  test('no horizontal overflow at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
