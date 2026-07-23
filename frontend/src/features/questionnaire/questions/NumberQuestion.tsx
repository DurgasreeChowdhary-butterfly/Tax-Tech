import { useState } from 'react'
import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

/** Answer value shape: a JSON integer, not a string (backend validation.py's
 * NUMBER branch does `isinstance(value, int)`) — the raw input text is
 * parsed here so the wire payload is a number, never `"3"`. */
export function NumberQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  const [text, setText] = useState('')
  const parsed = text.trim() === '' ? null : Number.parseInt(text, 10)
  const canSubmit = parsed !== null && Number.isInteger(parsed) && String(parsed) === text.trim()

  return (
    <QuestionShell
      question={question}
      submitting={submitting}
      canSubmit={canSubmit}
      onSubmit={() => onSubmit(parsed)}
    >
      <label className="sr-only" htmlFor="number-answer">
        {question.prompt}
      </label>
      <input
        id="number-answer"
        type="number"
        step={1}
        inputMode="numeric"
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full rounded-lg border border-gray-300 px-3 py-3 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
      />
    </QuestionShell>
  )
}
