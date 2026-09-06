import { expect, test } from '@playwright/test';

const api = 'http://localhost:8000';

async function mockProductivityApi(page: import('@playwright/test').Page, role: 'faculty' | 'admin' = 'faculty') {
  await page.addInitScript(() => {
    window.sessionStorage.setItem('ecai_access_token', 'e2e-access');
    window.sessionStorage.setItem('ecai_refresh_token', 'e2e-refresh');
  });

  await page.route(`${api}/api/**`, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });

    if (path === '/api/auth/me') {
      return json({ user_id: `${role}-1`, email: `${role}@example.com`, full_name: role, roles: [role], is_active: true });
    }
    if (path === '/api/productivity/jobs') {
      return json({ jobs: [{ id: 'job-1', status: 'completed', current_step: 'Ready for review', progress_percent: 100, retry_count: 0, error_message: null, paper_id: 'paper-1', total_questions: 10, created_at: null, finished_at: null }] });
    }
    if (path === '/api/productivity/templates' && route.request().method() === 'POST') {
      return json({ id: 'template-2', name: 'New template', description: null, created_by: 'faculty-1', version: 1, template_json: {} }, 201);
    }
    if (path === '/api/productivity/templates') {
      return json({ templates: [{ id: 'template-1', name: 'Midterm', description: null, created_by: 'faculty-1', version: 1, template_json: {} }] });
    }
    if (path === '/api/papers/recent') {
      return json([{ id: 'paper-1', title: 'Algebra Midterm', subject: 'Algebra', exam_type: 'Midterm', total_marks: 50, duration_minutes: 90, status: 'draft', created_at: null, updated_at: null }]);
    }
    if (path === '/api/productivity/papers/paper-1/downloads') {
      return json({ downloads: [{ version_id: 'version-2', version_number: 2, pdf_available: true, docx_available: false }] });
    }
    if (path === '/api/productivity/papers/paper-1/versions') {
      return json({ versions: [{ id: 'version-2', version_number: 2, paper_json: {} }, { id: 'version-1', version_number: 1, paper_json: {} }] });
    }
    if (path === '/api/papers/drafts/paper-1') {
      return json({ id: 'paper-1', title: 'Algebra Midterm', status: 'draft', locked_question_numbers: [], locked_question_keys: [], paper_json: { questions: [], validation: { passed: true, issues: [] } }, validation_passed: true });
    }
    if (path === '/api/productivity/usage') {
      return role === 'admin'
        ? json({ generation_counts: { completed: 4, failed: 1 }, audit_activity: [{ action: 'clone_paper', entity_type: 'paper', created_at: null }] })
        : json({ detail: 'Insufficient permissions' }, 403);
    }
    if (path.endsWith('/versions/version-1/restore')) return json({ version_id: 'version-3' });
    if (path.endsWith('/clone')) return json({ source_paper_id: 'paper-1', paper_id: 'paper-2', title: 'Algebra Midterm (Copy)', paper_json: {} });
    return json({});
  });
}

test('productivity center shows jobs, templates, search, downloads, and clone action', async ({ page }) => {
  await mockProductivityApi(page);
  await page.goto('/productivity');
  await expect(page.getByRole('heading', { name: 'Productivity center' })).toBeVisible();
  await expect(page.getByText('Ready for review')).toBeVisible();
  await expect(page.getByText('Midterm')).toBeVisible();
  await expect(page.getByText('PDF')).toBeVisible();
  await page.getByLabel('Template name').fill('New template');
  await page.getByRole('button', { name: 'Save' }).click();
  await page.getByRole('button', { name: /clone/i }).click();
  await expect(page).toHaveURL(/\/review\?paper_id=paper-2/);
});

test('review shows version history and restores an older version', async ({ page }) => {
  await mockProductivityApi(page);
  await page.goto('/review?paper_id=paper-1');
  await expect(page.getByTestId('version-history')).toBeVisible();
  await expect(page.getByText('Version 1')).toBeVisible();
  await page.getByRole('button', { name: 'Restore' }).click();
  await expect(page.getByText('Version restored as a new auditable version.')).toBeVisible();
});

test('admin usage is visible only to administrators', async ({ browser }) => {
  const faculty = await browser.newPage();
  await mockProductivityApi(faculty, 'faculty');
  await faculty.goto('/admin');
  await expect(faculty.getByTestId('admin-denied')).toBeVisible();
  await faculty.close();

  const admin = await browser.newPage();
  await mockProductivityApi(admin, 'admin');
  await admin.goto('/admin');
  await expect(admin.getByTestId('admin-usage')).toContainText('completed: 4');
  await admin.getByTestId('tab-audit').click();
  await expect(admin.getByTestId('usage-audit-activity')).toContainText('clone paper');
});
