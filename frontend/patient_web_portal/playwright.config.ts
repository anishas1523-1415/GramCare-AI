import { defineConfig, devices } from '@playwright/test';

/**
 * Smoke suite: login -> dashboard -> one core action, per role. Exists
 * because every gap this caught during live manual testing (silent 403s,
 * missing profile pages, a role missing from the registration dropdown)
 * was invisible to the backend's pytest suite by construction — none of
 * those bugs lived in the API, they lived in whether the frontend called
 * the API at all. Requires a running backend seeded via
 * apps/backend_service/scripts/seed_e2e_users.py (see e2e/README.md).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run build && npm run start',
    url: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
