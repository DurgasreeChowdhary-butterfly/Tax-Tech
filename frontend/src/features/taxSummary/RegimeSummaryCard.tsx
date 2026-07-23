import { Link } from 'react-router-dom'
import { formatCurrency } from '../../utils/format'
import type { TaxCalculationRead } from '../../types/api'

const REGIME_LABEL: Record<TaxCalculationRead['regime'], string> = {
  OLD: 'Old regime',
  NEW: 'New regime',
}

/** Renders one regime's already-computed totals verbatim. Deliberately does
 * not compare this card's numbers against the other regime's, and shows no
 * "recommended"/"cheaper" badge — the backend does not return a
 * recommendation, and this app must never decide one itself. */
export function RegimeSummaryCard({ calculation, filingSessionId }: { calculation: TaxCalculationRead; filingSessionId: string }) {
  const isRefund = calculation.net_payable.trim().startsWith('-')
  const netAmount = isRefund ? calculation.net_payable.replace('-', '') : calculation.net_payable

  return (
    <div
      data-testid={`regime-summary-${calculation.regime}`}
      className="flex flex-1 flex-col gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-800"
    >
      <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{REGIME_LABEL[calculation.regime]}</p>

      <dl className="flex flex-col gap-2 text-sm">
        <div className="flex justify-between gap-2">
          <dt className="text-gray-600 dark:text-gray-300">Taxable income</dt>
          <dd className="font-medium text-gray-900 dark:text-gray-100">{formatCurrency(calculation.taxable_income)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-gray-600 dark:text-gray-300">Total tax liability</dt>
          <dd className="font-medium text-gray-900 dark:text-gray-100">{formatCurrency(calculation.total_tax_liability)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-gray-600 dark:text-gray-300">{isRefund ? 'Estimated refund' : 'Estimated tax payable'}</dt>
          <dd className="font-medium text-gray-900 dark:text-gray-100">{formatCurrency(netAmount)}</dd>
        </div>
      </dl>

      <Link
        to={`/filing-sessions/${filingSessionId}/tax-summary/${calculation.regime}`}
        className="text-sm font-medium text-blue-700 dark:text-blue-400"
      >
        View full summary
      </Link>
    </div>
  )
}
