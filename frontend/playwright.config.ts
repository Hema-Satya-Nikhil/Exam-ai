import { defineConfig } from '@playwright/test';

/**
 * Browser E2E config for the composite Review workflow.
 *
 * Prerequisites (started separately, not auto-managed):
 *   1. Backend  : uvicorn app.main:app --port 8000   (from backend/, real or stub provider)
 *   2. Frontend : npm run dev                        (from frontend/, port 3000)
 *   3. A generated composite paper id:
 *        npm run e2e:seed          -> seeds one via the backend API and prints it
 *        E2E_PAPER_ID=<id> npm run e2e
 *
 * Specs that need a paper are skipped (with a clear message) when
 * E2E_PAPER_ID is not set, so `npm run e2e` never fails spuriously.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 240_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
  },
});
