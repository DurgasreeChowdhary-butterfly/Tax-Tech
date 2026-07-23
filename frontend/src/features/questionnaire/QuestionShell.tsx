import type { FormEvent, ReactNode } from 'react'
import { Button } from '../../components/ui/Button'
import type { QuestionRead } from '../../types/api'

interface QuestionShellProps {
  question: QuestionRead
  submitting: boolean
  canSubmit: boolean
  onSubmit: () => void
  children: ReactNode
}

/** Chrome shared by every question type: the prompt, the type-specific
 * input (passed as children), and the Continue button — "one question,
 * answer input, Continue button, loading state" per screen. */
export function QuestionShell({ question, submitting, canSubmit, onSubmit, children }: QuestionShellProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6" aria-busy={submitting}>
      <div>
        <p className="text-xl font-medium text-gray-900 dark:text-gray-100">{question.prompt}</p>
        {!question.is_required && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Optional</p>}
      </div>
      {children}
      <Button type="submit" disabled={!canSubmit || submitting} loading={submitting}>
        Continue
      </Button>
    </form>
  )
}
