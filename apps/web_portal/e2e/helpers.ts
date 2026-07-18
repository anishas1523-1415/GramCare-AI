import { Page, expect } from '@playwright/test';

export const E2E_PASSWORD = 'E2ETestPass123!';

/** Logs in via the real /login form (not a localStorage shortcut) — the
 * point of this suite is catching gaps in the login->dashboard path
 * itself, so it has to actually exercise that path. Waits for the
 * post-login redirect to actually land before returning: every role
 * navigates away from /login on success, so a caller that immediately
 * does something else (a fresh page.goto, not an assertion that would
 * itself retry/wait) can otherwise race the still-in-flight login/me
 * calls and cancel them. */
export async function login(page: Page, username: string) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(E2E_PASSWORD);
  // The page also has a Sign In / Register mode-toggle tab with the same
  // accessible name — scope to the form's actual submit button.
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
}

// The realtime signaling service behind NEXT_PUBLIC_WS_URL (SOS broadcast,
// video-consult WebRTC) is a separate Node deployment outside this repo —
// unreachable from a local/CI E2E run by design (nothing listens on
// localhost:4000 here, and the production onrender.com fallback isn't
// reachable either), so socket.io's connection attempts to it are expected
// noise, not a regression to catch.
const IGNORED_CONSOLE_ERROR_HOSTS = ['localhost:4000', 'onrender.com'];

/** Call at the start of a test; call the returned function at the end to
 * assert nothing logged a console error in between. */
export function watchConsoleErrors(page: Page) {
  const errors: string[] = [];
  const failedHosts: string[] = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('requestfailed', (req) => {
    try {
      failedHosts.push(new URL(req.url()).host);
    } catch {
      // opaque/relative URL — nothing to correlate
    }
  });

  return () => {
    const real = errors.filter((e) => {
      if (!e.includes('ERR_CONNECTION_REFUSED')) return true;
      return !failedHosts.some((h) => IGNORED_CONSOLE_ERROR_HOSTS.some((ignored) => h.includes(ignored)));
    });
    expect(real, `Console errors: ${real.join('\n')}`).toEqual([]);
  };
}
