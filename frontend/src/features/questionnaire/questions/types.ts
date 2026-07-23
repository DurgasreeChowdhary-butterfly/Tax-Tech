import type { QuestionRead } from '../../../types/api'

export interface QuestionComponentProps {
  question: QuestionRead
  submitting: boolean
  onSubmit: (value: unknown) => void
  /** Only used by DOCUMENT_UPLOAD/REVIEW_CARD (features/documents,
   * features/review) — those two question types orchestrate calls to the
   * document/extraction APIs, which are scoped by filing session rather
   * than by question. Every other question type ignores this prop. */
  filingSessionId: string
}
