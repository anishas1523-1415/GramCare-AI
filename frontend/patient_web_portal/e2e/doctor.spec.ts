import { test, expect } from '@playwright/test';
import { login, watchConsoleErrors } from './helpers';

test('approved doctor logs in and reaches the real dashboard, not the review gate', async ({ page }) => {
  const checkErrors = watchConsoleErrors(page);

  await login(page, 'e2e_doctor');
  await expect(page).toHaveURL(/\/doctor\/dashboard/);

  // The exact regression this suite exists to catch: an approved doctor
  // landing on the "Application Under Review" gate instead of their queue.
  await expect(page.getByText('Application Under Review')).not.toBeVisible();
  await expect(page.getByRole('heading', { name: /Welcome, Dr\./ })).toBeVisible();

  await page.getByRole('link', { name: 'My Profile' }).click();
  await expect(page).toHaveURL(/\/doctor\/profile/);
  await expect(page.getByText('Approved', { exact: true })).toBeVisible();

  checkErrors();
});
