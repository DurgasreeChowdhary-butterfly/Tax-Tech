import { useState } from 'react'
import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

/** Answer value shape: the chosen option's `value` string — must be one of
 * `question.options[].value` (backend validation.py's SINGLE_CHOICE branch;
 * enforced authoritatively there, this UI just can't submit anything else). */
export function SingleChoiceQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  const [value, setValue] = useState<string | null>(null)

  return (
    <QuestionShell question={question} submitting={submitting} canSubmit={value !== null} onSubmit={() => onSubmit(value)}>
      <div role="radiogroup" aria-label={question.prompt} className="flex flex-col gap-2">
        {question.options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            onClick={() => setValue(option.value)}
            className={`rounded-lg border px-4 py-3 text-left text-base font-medium ${
              value === option.value
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
