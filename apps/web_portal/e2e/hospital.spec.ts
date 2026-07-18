import { test, expect } from '@playwright/test';
import { login, watchConsoleErrors } from './helpers';

test('hospital account logs in, reaches the Emergency Desk, and can register its profile', async ({ page }) => {
  const checkErrors = watchConsoleErrors(page);

  await login(page, 'e2e_hospital');
  await expect(page).toHaveURL(/\/hospital$/);
  await expect(page.getByRole('heading', { name: 'Emergency Desk' })).toBeVisible();

  await page.getByRole('link', { name: 'Hospital Profile' }).click();
  await expect(page).toHaveURL(/\/hospital\/profile/);
  await expect(page.getByRole('heading', { name: /Hospital Profile|Register Your Hospital/ })).toBeVisible();

  checkErrors();
});
