import { QuestionShell } from '../QuestionShell'
import type { QuestionComponentProps } from './types'

/** No real answer payload — the backend accepts anything for INFORMATION
 * questions (validation.py). Continue just acknowledges the user has read
 * the prompt. */
export function InformationQuestion({ question, submitting, onSubmit }: QuestionComponentProps) {
  return (
    <QuestionShell question={question} submitting={submitting} canSubmit onSubmit={() => onSubmit(null)}>
      <></>
    </QuestionShell>
  )
}
