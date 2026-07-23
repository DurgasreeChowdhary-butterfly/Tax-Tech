import { useState } from 'react'
import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

/** Answer value shape: a plain boolean — see backend/app/engines/
 * questionnaire/validation.py's BOOLEAN branch. */
export function BooleanQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  const [value, setValue] = useState<boolean | null>(null)

  return (
    <QuestionShell question={question} submitting={submitting} canSubmit={value !== null} onSubmit={() => onSubmit(value)}>
      <div role="radiogroup" aria-label={question.prompt} className="flex gap-3">
        {[
          { label: 'Yes', v: true },
          { label: 'No', v: false },
        ].map((option) => (
          <button
            key={option.label}
            type="button"
            role="radio"
            aria-checked={value === option.v}
            onClick={() => setValue(option.v)}
            className={`flex-1 rounded-lg border px-4 py-3 text-base font-medium ${
              value === option.v
                ? 'border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                : 'border-gray-300 text-gray-700 dark:border-gray-700 dark:text-gray-200'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </QuestionShell>
  )
}
