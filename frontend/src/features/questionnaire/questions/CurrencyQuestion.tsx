import { useState } from 'react'
import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

// Light UX pre-check only — a non-negative number with at most 2 decimal
// places "looks like" a valid amount. The backend (validation.py's
// CURRENCY branch) is the authoritative parser/validator; this regex exists
// only to keep the Continue button disabled for obviously-wrong input, not
// to replicate the backend's Decimal rules.
const LOOKS_LIKE_AMOUNT = /^\d+(\.\d{1,2})?$/

/** Answer value shape: a decimal amount as a STRING (e.g. "1234.56"), never
 * a float — matches this project's Decimal-only rule for money (CLAUDE.md)
 * all the way down to the raw capture payload. */
export function CurrencyQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  const [text, setText] = useState('')
  const canSubmit = LOOKS_LIKE_AMOUNT.test(text.trim())

  return (
    <QuestionShell question={question} submitting={submitting} canSubmit={canSubmit} onSubmit={() => onSubmit(text.trim())}>
      <label className="sr-only" htmlFor="currency-answer">
        {question.prompt}
      </label>
      <div className="flex items-center gap-2">
        <span className="text-base text-gray-500 dark:text-gray-400">₹</span>
        <input
          id="currency-answer"
          type="text"
          inputMode="decimal"
          placeholder="0.00"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-lg border border-gray-300 px-3 py-3 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        />
      </div>
    </QuestionShell>
  )
}
