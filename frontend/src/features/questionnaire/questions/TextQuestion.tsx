import { useState } from 'react'
import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

/** Answer value shape: a plain string, non-empty if the question is
 * required (backend validation.py's TEXT branch). */
export function TextQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  const [value, setValue] = useState('')
  const canSubmit = !question.is_required || value.trim().length > 0

  return (
    <QuestionShell question={question} submitting={submitting} canSubmit={canSubmit} onSubmit={() => onSubmit(value)}>
      <label className="sr-only" htmlFor="text-answer">
        {question.prompt}
      </label>
      <textarea
        id="text-answer"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={4}
        className="w-full rounded-lg border border-gray-300 px-3 py-3 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
      />
    </QuestionShell>
  )
}
