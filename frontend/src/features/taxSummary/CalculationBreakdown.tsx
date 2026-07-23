import { formatCurrency, humanizeLabel } from '../../utils/format'
import type { CalculationLineItemRead, TaxCalculationRead } from '../../types/api'

const SUMMARY_ROWS: { key: keyof TaxCalculationRead; label: string }[] = [
  { key: 'gross_total_income', label: 'Gross total income' },
  { key: 'total_deductions_applied', label: 'Deductions applied' },
  { key: 'taxable_income', label: 'Taxable income' },
  { key: 'tax_before_rebate', label: 'Tax before rebate' },
  { key: 'rebate_amount', label: 'Rebate' },
  { key: 'tax_after_rebate', label: 'Tax after rebate' },
  { key: 'cess_amount', label: 'Cess' },
  { key: 'total_tax_liability', label: 'Total tax liability' },
  { key: 'total_tds_credit', label: 'TDS credit' },
]

/**
 * Renders a TaxCalculationResponse verbatim: the fixed summary fields the
 * backend returns, plus its full itemized line_items breakdown. No figure
 * here is computed, rounded, or re-derived in this component — every number
 * is exactly what backend/app/engines/tax/calculation.py produced.
 */
export function CalculationBreakdown({
  calculation,
  lineItems,
}: {
  calculation: TaxCalculationRead
  lineItems: CalculationLineItemRead[]
}) {
  const isRefund = calculation.net_payable.trim().startsWith('-')
  const netAmount = isRefund ? calculation.net_payable.replace('-', '') : calculation.net_payable

  return (
    <div className="flex flex-col gap-6">
      <dl data-testid="calculation-summary" className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4 text-sm dark:border-gray-800">
        {SUMMARY_ROWS.map(({ key, label }) => (
          <div key={key} className="flex justify-between gap-2">
            <dt className="text-gray-600 dark:text-gray-300">{label}</dt>
            <dd className="font-medium text-gray-900 dark:text-gray-100">{formatCurrency(String(calculation[key]))}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-2 border-t border-gray-200 pt-2 dark:border-gray-800">
          <dt className="font-medium text-gray-900 dark:text-gray-100">
            {isRefund ? 'Estimated refund' : 'Estimated tax payable'}
          </dt>
          <dd className="font-semibold text-gray-900 dark:text-gray-100">{formatCurrency(netAmount)}</dd>
        </div>
      </dl>

      {lineItems.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Calculation details</p>
          <ul className="flex flex-col gap-1 rounded-lg border border-gray-200 p-4 text-sm dark:border-gray-800">
            {[...lineItems]
              .sort((a, b) => a.sequence_index - b.sequence_index)
              .map((item, index) => (
                <li key={`${item.step_code}-${index}`} className="flex justify-between gap-2">
                  <span className="text-gray-600 dark:text-gray-300">{humanizeLabel(item.step_code)}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{formatCurrency(item.amount)}</span>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  )
}
