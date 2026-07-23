import { useState } from 'react'
import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

/** Answer value shape: a non-empty array of chosen `value` strings, no
 * duplicates (backend validation.py's MULTI_CHOICE branch). */
export function MultiChoiceQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  const [selected, setSelected] = useState<string[]>([])

  function toggle(optionValue: string) {
    setSelected((current) =>
      current.includes(optionValue) ? current.filter((v) => v !== optionValue) : [...current, optionValue],
    )
  }

  return (
    <QuestionShell
      question={question}
      submitting={submitting}
      canSubmit={selected.length > 0}
      onSubmit={() => onSubmit(selected)}
    >
      <div className="flex flex-col gap-2">
        {question.options.map((option) => {
          const checked = selected.includes(option.value)
          return (
            <label
              key={option.value}
              className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-base font-medium ${
                checked
                  ? 'border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                  : 'border-gray-300 text-gray-700 dark:border-gray-700 dark:text-gray-200'
              }`}
            >
              <input type="checkbox" checked={checked} onChange={() => toggle(option.value)} className="h-4 w-4" />
              {option.label}
            </label>
          )
        })}
      </div>
    </QuestionShell>
  )
}
