import { test, expect } from '@playwright/test';
import { login, watchConsoleErrors } from './helpers';

test('patient logs in and reaches the symptom checker', async ({ page }) => {
  const checkErrors = watchConsoleErrors(page);

  await login(page, 'e2e_patient');
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('heading', { name: /GramCare/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Analyze with AI/i })).toBeVisible();

  await page.getByRole('link', { name: 'Family Profiles' }).click();
  await expect(page).toHaveURL(/\/family/);

  checkErrors();
});

test('patient without a phone on file can add one for SMS reminders from the booking page', async ({ page }) => {
  // e2e_patient is seeded without a phone (registration never collects one
  // for PATIENT) — this is the only surface that can add it after the
  // fact. The real PUT is intercepted rather than let through: it would
  // permanently set the shared fixture user's phone, making this test not
  // safely re-runnable against a DB that isn't freshly reseeded.
  let capturedBody: unknown = null;
  await page.route('**/api/v1/auth/me/phone', async (route) => {
    capturedBody = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Phone number updated', phone: '+919000012345' }) });
  });

  await login(page, 'e2e_patient');
  await page.goto('/book');

  const banner = page.getByText('Get an SMS reminder before your appointment');
  await expect(banner).toBeVisible();

  await page.getByLabel('Phone number for SMS reminders').fill('+919000012345');
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(page.getByText("Phone number saved")).toBeVisible();
  expect(capturedBody).toEqual({ phone: '+919000012345' });
});
