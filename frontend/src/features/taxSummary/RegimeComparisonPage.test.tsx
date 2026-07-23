import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RegimeComparisonPage } from './RegimeComparisonPage'
import { supportedCaseApi } from '../../api/supportedCase'
import { taxCalculationApi } from '../../api/taxCalculation'
import { ApiError } from '../../api/client'
import type { TaxCalculationRead } from '../../types/api'

vi.mock('../../api/supportedCase', () => ({ supportedCaseApi: { get: vi.fn() } }))
vi.mock('../../api/taxCalculation', () => ({ taxCalculationApi: { getCalculation: vi.fn() } }))

const mockedSupportedCaseApi = vi.mocked(supportedCaseApi)
const mockedTaxCalculationApi = vi.mocked(taxCalculationApi)

function calculation(overrides: Partial<TaxCalculationRead>): TaxCalculationRead {
  return {
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
    ...overrides,
  }
}

const FILING_SESSION_ID = 'fs-1'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/filing-sessions/${FILING_SESSION_ID}/regime-comparison`]}>
      <Routes>
        <Route path="/filing-sessions/:filingSessionId/regime-comparison" element={<RegimeComparisonPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RegimeComparisonPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders both regimes verbatim, with no local "which is better" comparison', async () => {
    mockedSupportedCaseApi.get.mockResolvedValue({ outcome: 'SUPPORTED', reasons: [] })
    mockedTaxCalculationApi.getCalculation.mockImplementation((_id, regime) =>
      Promise.resolve({ calculation: calculation({ regime, net_payable: regime === 'OLD' ? '9000.00' : '-2000.00' }), line_items: [] }),
    )

    renderPage()

    expect(await screen.findByText('Old regime')).toBeInTheDocument()
    expect(screen.getByText('New regime')).toBeInTheDocument()
    expect(screen.getByText('₹9000.00')).toBeInTheDocument() // OLD: payable
    expect(screen.getByText('₹2000.00')).toBeInTheDocument() // NEW: refund (sign stripped for display)
    expect(screen.getByText('Estimated refund')).toBeInTheDocument()
    expect(screen.getByText('Estimated tax payable')).toBeInTheDocument()
    // No recommendation/"cheaper" language anywhere on the page.
    expect(screen.queryByText(/recommend/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/cheaper/i)).not.toBeInTheDocument()
  })

  it('shows the backend-provided blocking message instead of a number when not SUPPORTED', async () => {
    mockedSupportedCaseApi.get.mockResolvedValue({ outcome: 'INCOMPLETE', reasons: ['NO_VERIFIED_INCOME'] })

    renderPage()

    expect(await screen.findByText('A few more details are needed')).toBeInTheDocument()
    expect(screen.getByText('No verified income')).toBeInTheDocument()
    expect(mockedTaxCalculationApi.getCalculation).not.toHaveBeenCalled()
  })

  it('shows a retryable error state when the supported-case check fails', async () => {
    mockedSupportedCaseApi.get.mockRejectedValue(new ApiError(500, 'Something went wrong'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
