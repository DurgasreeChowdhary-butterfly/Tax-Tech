import { humanizeLabel } from '../../utils/format'
import type { SupportedCaseOutcome } from '../../types/api'

/** Fixed copy per outcome, matching docs/TAX_ENGINE_BOUNDARY.md's own
 * language for each state — never a computed or guessed tax figure appears
 * here. The backend decides the outcome and the reasons; this only labels
 * the enum value itself. */
const OUTCOME_COPY: Record<Exclude<SupportedCaseOutcome, 'SUPPORTED'>, { title: string; description: string }> = {
  REVIEW_REQUIRED: {
    title: 'Your filing needs manual review',
    description: 'Some of your answers mean this case needs a human review before a tax estimate can be produced.',
  },
  NOT_SUPPORTED: {
    title: "This filing isn't supported yet",
    description: 'Your situation falls outside what this app can currently estimate.',
  },
  INCOMPLETE: {
    title: 'A few more details are needed',
    description: 'Some required information is still missing before an estimate can be produced.',
  },
}

export function SupportedCaseBlocked({ outcome, reasons }: { outcome: Exclude<SupportedCaseOutcome, 'SUPPORTED'>; reasons: string[] }) {
  const copy = OUTCOME_COPY[outcome]
  return (
    <div className="mx-auto flex w-full max-w-md flex-col items-center gap-3 p-6 text-center">
      <p className="text-lg font-medium text-gray-900 dark:text-gray-100">{copy.title}</p>
      <p className="text-sm text-gray-600 dark:text-gray-300">{copy.description}</p>
      {reasons.length > 0 && (
        <ul className="mt-2 flex w-full flex-col gap-1 text-left text-sm text-gray-600 dark:text-gray-300">
          {reasons.map((reason) => (
            <li key={reason} className="rounded-md bg-gray-100 px-3 py-2 dark:bg-gray-800">
              {humanizeLabel(reason)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
