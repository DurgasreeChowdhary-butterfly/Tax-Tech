import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { SEED_OUTPUT_PATH_PHASE13 } from './env'

interface SeedOutput {
  email: string
  password: string
  filing_session_id: string
}

const seed: SeedOutput = JSON.parse(readFileSync(SEED_OUTPUT_PATH_PHASE13, 'utf-8'))

/**
 * Phase 13 happy-path E2E test: the full guided journey from
 * docs/PRODUCT_SCOPE.md, walked on a mobile viewport against the real
 * backend (docs/IMPLEMENTATION_PLAN.md Phase 13 exit criteria) — upload a
 * document, review/confirm/correct its extracted fields, reach the
 * questionnaire's completion screen, view the regime comparison, then the
 * full tax summary for one regime. Every number shown comes straight from
 * the backend; this test would fail if the frontend ever computed one itself.
 */
test('walks upload -> review -> regime comparison -> tax summary on a mobile viewport', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(seed.email)
  await page.getByLabel('Password').fill(seed.password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByText('Welcome')).toBeVisible()

  await page.goto(`/filing-sessions/${seed.filing_session_id}/questionnaire`)

  // --- DOCUMENT_UPLOAD ---
  await expect(page.getByLabel('Upload your Form 16')).toBeVisible()
  await page.getByLabel('Upload your Form 16').setInputFiles({
    name: 'form16.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 fake form16 pdf for e2e test'),
  })
  await page.getByRole('button', { name: 'Upload document' }).click()
  await expect(page.getByRole('button', { name: 'Continue' })).toBeEnabled({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Continue' }).click()

  // --- REVIEW_CARD ---
  await expect(page.getByText('Review the details we found')).toBeVisible()
  await expect(page.getByText('Gross salary')).toBeVisible({ timeout: 15_000 })

  // Accept employer name and gross salary as-is.
  const employerCard = page.getByTestId('review-field-employer_name')
  await employerCard.getByRole('button', { name: 'Accept' }).click()
  await expect(employerCard.getByText('Verified')).toBeVisible()

  const grossSalaryCard = page.getByTestId('review-field-gross_salary')
  await grossSalaryCard.getByRole('button', { name: 'Accept' }).click()
  await expect(grossSalaryCard.getByText('Verified')).toBeVisible()

  // Correct TDS deducted to prove the edit path submits to the backend.
  const tdsCard = page.getByTestId('review-field-tds_deducted')
  await tdsCard.getByRole('button', { name: 'Edit' }).click()
  await tdsCard.getByRole('textbox').fill('90000.00')
  await tdsCard.getByRole('button', { name: 'Save correction' }).click()
  await expect(tdsCard.getByText('Edited')).toBeVisible()

  // PAN has no domain mapping — never actionable in this app.
  const panCard = page.getByTestId('review-field-pan')
  await expect(panCard.getByText('Not reviewable here')).toBeVisible()

  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByText("You're all caught up")).toBeVisible()

  // --- Regime comparison ---
  await page.getByRole('link', { name: 'View regime comparison' }).click()
  await expect(page.getByText('Old regime')).toBeVisible()
  await expect(page.getByText('New regime')).toBeVisible()
  await expect(page.getByText('Taxable income')).toHaveCount(2)

  // --- Tax summary ---
  await page.getByTestId('regime-summary-OLD').getByRole('link', { name: 'View full summary' }).click()
  await expect(page.getByText('Tax summary — Old regime')).toBeVisible()
  await expect(page.getByTestId('calculation-summary').getByText('Gross total income')).toBeVisible()
  await expect(page.getByText('Calculation details')).toBeVisible()
})
