import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { SEED_OUTPUT_PATH } from './env'

interface SeedOutput {
  email: string
  password: string
  filing_session_id: string
}

const seed: SeedOutput = JSON.parse(readFileSync(SEED_OUTPUT_PATH, 'utf-8'))

/**
 * Phase 12 happy-path E2E test: log in, then walk the real backend's Phase 3
 * mini question graph (has_other_income -> filing_intent -> confirm_ready,
 * per backend/app/tests/conftest.py::questionnaire_fixture and
 * backend/app/tests/test_questionnaire_api.py) to completion, on a mobile
 * viewport (see playwright.config.ts's "mobile" project). Every question
 * shown and every "next question" advanced to comes from the backend's own
 * response — this test would fail if the frontend ever started guessing.
 */
test('logs in and completes the mini questionnaire on a mobile viewport', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(seed.email)
  await page.getByLabel('Password').fill(seed.password)
  await page.getByRole('button', { name: 'Log in' }).click()

  await expect(page.getByText('Welcome')).toBeVisible()

  await page.goto(`/filing-sessions/${seed.filing_session_id}/questionnaire`)

  await expect(page.getByText('Do you have any other income sources?')).toBeVisible()
  await page.getByRole('radio', { name: 'No' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(page.getByText('How would you like to proceed?')).toBeVisible()
  await page.getByRole('radio', { name: 'Quick estimate' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(page.getByText('Ready to see your summary?')).toBeVisible()
  await page.getByRole('radio', { name: 'Yes' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(page.getByText("You're all caught up")).toBeVisible()
})
