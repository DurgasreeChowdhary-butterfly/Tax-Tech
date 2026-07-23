import { useState } from 'react'
import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

/** Answer value shape: an ISO date string "YYYY-MM-DD" (backend
 * validation.py's DATE branch) — a native `<input type="date">` already
 * produces exactly that string, so no reformatting is needed here. */
export function DateQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  const [value, setValue] = useState('')

  return (
    <QuestionShell
      question={question}
      submitting={submitting}
      canSubmit={value.trim().length > 0}
      onSubmit={() => onSubmit(value)}
    >
      <label className="sr-only" htmlFor="date-answer">
        {question.prompt}
      </label>
      <input
        id="date-answer"
        type="date"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="w-full rounded-lg border border-gray-300 px-3 py-3 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
      />
    </QuestionShell>
  )
}
