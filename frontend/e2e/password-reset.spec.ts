import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import { execSync } from 'node:child_process';
import { resolve } from 'node:path';

/**
 * Password-reset E2E — full OTP round trip.
 *
 * Requires the backend to run with APP_ENV=TEST so that:
 *   - email delivery uses the NoopEmailService (no real mail), and
 *   - the TEST-only outbox routes are mounted.
 *
 * The test is SELF-RESEEDING: a beforeAll runs the seeder so the account
 * always starts from the known initial password, regardless of how many prior
 * runs changed it. This keeps the round-trip deterministic.
 *
 * The test account is e2e.reset.faculty@test.com (active faculty).
 */

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000';
const TEST_EMAIL = 'e2e.reset.faculty@test.com';
const OLD_PASSWORD = process.env.E2E_INITIAL_PASSWORD || 'E2eResetPass1!';
const NEW_PASSWORD = process.env.E2E_NEW_PASSWORD || 'E2eResetPass2!';

/** Seed the deterministic test user to the known initial password. */
function seedTestUser(): void {
  const backendDir = resolve(__dirname, '../../backend');
  const script = resolve(backendDir, 'e2e_seed_reset_user.py');
  // Prefer the project venv python (matches the e2e:seed:reset npm script).
  const venvPython = resolve(__dirname, '../../.venv/Scripts/python.exe');
  const python = process.env.E2E_PYTHON || venvPython || 'python';
  execSync(`"${python}" "${script}"`, { stdio: 'pipe', cwd: backendDir });
}

test.beforeAll(() => {
  try {
    seedTestUser();
  } catch (err) {
    // The seeder requires a live database (APP_ENV=TEST backend). Surface a
    // clear warning rather than failing cryptically.
    console.warn('[password-reset e2e] reseed failed; will rely on existing state', String(err));
  }
});

async function gotoLogin(page: Page): Promise<void> {
  await page.goto('/login');
  await expect(page.getByTestId('forgot-password-link')).toBeVisible();
}

/** Fetch the most recent OTP the Noop adapter recorded for the test email. */
async function fetchOtp(request: APIRequestContext): Promise<string> {
  const resp = await request.get(`${API_BASE}/api/auth/test/outbox`, {
    params: { email: TEST_EMAIL },
  });
  expect(resp.status(), await resp.text()).toBe(200);
  const body = (await resp.json()) as { messages: Array<{ email: string; otp: string }> };
  expect(body.messages.length).toBeGreaterThan(0);
  return body.messages[0].otp;
}

async function loginViaApi(request: APIRequestContext, email: string, password: string) {
  return request.post(`${API_BASE}/api/auth/login`, {
    data: { email, password },
  });
}

test('login page exposes the Forgot Password link', async ({ page }) => {
  await gotoLogin(page);
  await expect(page.getByTestId('forgot-password-link')).toHaveAttribute(
    'href',
    '/forgot-password'
  );
});

test('full password reset round-trip via UI + TEST outbox', async ({ page, request }) => {
  // 1. Old password currently signs in (sanity, matches the seeded state).
  const before = await loginViaApi(request, TEST_EMAIL, OLD_PASSWORD);
  expect(before.status()).toBe(200);

  // 2. Login → Forgot Password.
  await gotoLogin(page);
  await page.getByTestId('forgot-password-link').click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(page.getByRole('heading', { name: 'Forgot Password' })).toBeVisible();

  // 3. Enter the test email → submit → OTP step (no state in the URL).
  await page.getByTestId('forgot-email').fill(TEST_EMAIL);
  await page.getByTestId('send-otp-button').click();
  await page.waitForURL(/\/verify-otp$/);
  // The $ anchor above ensures no query string (flow state never leaks via URL).
  await expect(page.getByRole('heading', { name: 'Verify OTP' })).toBeVisible();

  // 4. Retrieve the TEST-only OTP and enter it.
  const otp = await fetchOtp(request);
  await expect(otp).toMatch(/^\d{6}$/);
  for (let i = 0; i < 6; i += 1) {
    await page.getByTestId(`otp-digit-${i}`).fill(otp[i]);
  }

  // 5. Verify → reset-password step.
  await page.getByTestId('verify-otp-button').click();
  await page.waitForURL(/\/reset-password$/);
  await expect(page.getByRole('heading', { name: 'Reset Password' })).toBeVisible();

  // 6. Set the NEW password.
  await page.getByTestId('new-password').fill(NEW_PASSWORD);
  await page.getByTestId('confirm-password').fill(NEW_PASSWORD);
  await page.getByTestId('reset-password-button').click();

  // 7. Success card.
  await expect(page.getByTestId('reset-success')).toBeVisible();
  await expect(page.getByTestId('reset-success')).toContainText(
    'Your password has been reset successfully.'
  );

  // 8. NEW password logs in.
  const afterNew = await loginViaApi(request, TEST_EMAIL, NEW_PASSWORD);
  expect(afterNew.status()).toBe(200);
  const meResp = await request.get(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${(await afterNew.json())['access_token']}` },
  });
  expect(meResp.status()).toBe(200);
  const me = (await meResp.json()) as { roles: string[]; is_active: boolean };
  expect(me.roles).toContain('faculty');
  expect(me.is_active).toBe(true);

  // 9. OLD password no longer works (401).
  const afterOld = await loginViaApi(request, TEST_EMAIL, OLD_PASSWORD);
  expect(afterOld.status()).toBe(401);
});

test('forgot password → client-side validation, then generic OTP step', async ({ page, request }) => {
  await gotoLogin(page);
  await page.getByTestId('forgot-password-link').click();
  await expect(page).toHaveURL(/\/forgot-password$/);

  // invalid format rejected without an API call
  await page.getByTestId('forgot-email').fill('not-an-email');
  await page.getByTestId('send-otp-button').click();
  await expect(page.getByTestId('forgot-error')).toContainText(/valid email/i);

  // valid request → OTP step, no URL leakage, resend disabled.
  // Uses a non-existent email on purpose: it still walks the OTP step (generic
  // response, no enumeration) and avoids colliding with the round-trip test's
  // 60s resend cooldown on the real test account.
  await page.getByTestId('forgot-email').fill('someone.else@example.com');
  await page.getByTestId('send-otp-button').click();
  await page.waitForURL(/\/verify-otp$/);
  // The $ anchor ensures no query string leaks either.
  await expect(page.getByRole('heading', { name: 'Verify OTP' })).toBeVisible();
  for (let i = 0; i < 6; i += 1) {
    await expect(page.getByTestId(`otp-digit-${i}`)).toBeVisible();
  }
  await expect(page.getByTestId('resend-otp-button')).toBeDisabled();
});

test('verify-otp without flow state redirects back to /forgot-password', async ({ page }) => {
  await page.goto('/verify-otp');
  await page.waitForURL(/\/forgot-password$/);
});

test('reset-password without flow state redirects back to /forgot-password', async ({ page }) => {
  await page.goto('/reset-password');
  await page.waitForURL(/\/forgot-password$/);
});
