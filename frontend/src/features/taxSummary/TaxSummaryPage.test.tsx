import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TaxSummaryPage } from './TaxSummaryPage'
import { supportedCaseApi } from '../../api/supportedCase'
import { taxCalculationApi } from '../../api/taxCalculation'
import { ApiError } from '../../api/client'

vi.mock('../../api/supportedCase', () => ({ supportedCaseApi: { get: vi.fn() } }))
vi.mock('../../api/taxCalculation', () => ({ taxCalculationApi: { getCalculation: vi.fn() } }))

const mockedSupportedCaseApi = vi.mocked(supportedCaseApi)
const mockedTaxCalculationApi = vi.mocked(taxCalculationApi)

const FILING_SESSION_ID = 'fs-1'

function renderPage(regime: 'OLD' | 'NEW' = 'OLD') {
  return render(
    <MemoryRouter initialEntries={[`/filing-sessions/${FILING_SESSION_ID}/tax-summary/${regime}`]}>
      <Routes>
        <Route path="/filing-sessions/:filingSessionId/tax-summary/:regime" element={<TaxSummaryPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('TaxSummaryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders every backend-computed figure verbatim, including the itemized line items', async () => {
    mockedSupportedCaseApi.get.mockResolvedValue({ outcome: 'SUPPORTED', reasons: [] })
    mockedTaxCalculationApi.getCalculation.mockResolvedValue({
      calculation: {
        id: 'calc-1',
        regime: 'OLD',
        calculation_engine_version: 'v1',
        gross_total_income: '1200000.00',
        total_deductions_applied: '50000.00',
        taxable_income: '1150000.00',
        tax_before_rebate: '100000.00',
        rebate_amount: '0.00',
        tax_after_rebate: '100000.00',
        cess_amount: '4000.00',
        total_tax_liability: '104000.00',
        total_tds_credit: '95000.00',
        net_payable: '9000.00',
        created_at: '2026-01-01T00:00:00Z',
      },
      line_items: [
        { step_code: 'STANDARD_DEDUCTION_APPLIED', sequence_index: 1, amount: '50000.00', step_metadata: null },
        { step_code: 'SLAB_TAX:SLAB_1', sequence_index: 2, amount: '0.00', step_metadata: null },
      ],
    })

    renderPage('OLD')

    expect(await screen.findByText('Tax summary — Old regime')).toBeInTheDocument()
    expect(screen.getByText('₹1200000.00')).toBeInTheDocument() // gross total income
    expect(screen.getByText('₹1150000.00')).toBeInTheDocument() // taxable income
    expect(screen.getByText('₹104000.00')).toBeInTheDocument() // total tax liability
    expect(screen.getByText('Estimated tax payable')).toBeInTheDocument()
    expect(screen.getByText('Standard deduction applied')).toBeInTheDocument()
    expect(screen.getByText('Slab tax slab 1')).toBeInTheDocument()
  })

  it('shows the backend-provided blocking message when not SUPPORTED, never a partial figure', async () => {
    mockedSupportedCaseApi.get.mockResolvedValue({ outcome: 'NOT_SUPPORTED', reasons: ['FILER_CATEGORY_UNSUPPORTED'] })

    renderPage('NEW')

    expect(await screen.findByText("This filing isn't supported yet")).toBeInTheDocument()
    expect(screen.getByText('Filer category unsupported')).toBeInTheDocument()
    expect(mockedTaxCalculationApi.getCalculation).not.toHaveBeenCalled()
  })

  it('shows a retryable error state on failure', async () => {
    mockedSupportedCaseApi.get.mockRejectedValue(new ApiError(500, 'Something went wrong'))

    renderPage('OLD')

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
