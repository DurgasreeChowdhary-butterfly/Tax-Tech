import { useCallback, useEffect, useRef, useState } from 'react'
import { documentApi } from '../../api/documents'
import { extractionApi } from '../../api/extraction'
import { ApiError } from '../../api/client'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { Skeleton } from '../../components/ui/Skeleton'
import { QuestionShell } from '../questionnaire/QuestionShell'
import type { QuestionComponentProps } from '../questionnaire/questions/types'
import type { ReviewFieldRead, VerificationAction } from '../../types/api'
import { ReviewFieldCard } from './ReviewFieldCard'

/**
 * REVIEW_CARD question: lets the user confirm or correct the fields the
 * backend extracted from their most recently uploaded document
 * (backend/app/api/v1/extraction.py's /review and /fields/{id}/verify
 * endpoints). This component never decides what a "correct" value is, never
 * writes to salary_income/interest_income directly, and never keeps a
 * locally-edited value as if it were authoritative — every accept/edit is
 * submitted to the backend, and the field list is always re-fetched from
 * the backend afterward so the screen only ever shows verified backend state.
 */
export function ReviewCardQuestion({ question, submitting, onSubmit, filingSessionId }: QuestionComponentProps) {
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [fields, setFields] = useState<ReviewFieldRead[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busyFieldId, setBusyFieldId] = useState<string | null>(null)
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setLoading(true)
    setLoadError(null)
    try {
      const { documents } = await documentApi.list(filingSessionId)
      if (requestIdRef.current !== requestId) return

      const latest = documents
        .filter((d) => d.status === 'UPLOADED')
        .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0]

      if (!latest) {
        setDocumentId(null)
        setFields([])
        return
      }
      setDocumentId(latest.id)

      const reviewFields = await extractionApi.getReviewFields(filingSessionId, latest.id)
      if (requestIdRef.current !== requestId) return
      setFields(reviewFields)
    } catch (error) {
      if (requestIdRef.current === requestId) {
        setLoadError(error instanceof ApiError ? error.message : 'Could not load the extracted details.')
      }
    } finally {
      if (requestIdRef.current === requestId) {
        setLoading(false)
      }
    }
  }, [filingSessionId])

  useEffect(() => {
    void load()
    return () => {
      requestIdRef.current += 1
    }
  }, [load])

  async function handleVerify(fieldId: string, action: VerificationAction, value?: string) {
    if (!documentId) return
    setBusyFieldId(fieldId)
    try {
      await extractionApi.verifyField(filingSessionId, documentId, fieldId, { action, value })
      await load() // re-fetch: the backend's state is the only source of truth
    } catch (error) {
      setLoadError(error instanceof ApiError ? error.message : 'Could not save that. Please try again.')
    } finally {
      setBusyFieldId(null)
    }
  }

  const canSubmit = !loading && !loadError

  return (
    <QuestionShell question={question} submitting={submitting} canSubmit={canSubmit} onSubmit={() => onSubmit(null)}>
      {loading && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {!loading && loadError && <ErrorState message={loadError} onRetry={() => void load()} />}

      {!loading && !loadError && fields !== null && fields.length === 0 && (
        <EmptyState
          title="No documents to review yet"
          description="Upload a document first — once it's processed, its details will appear here for you to confirm."
        />
      )}

      {!loading && !loadError && fields !== null && fields.length > 0 && (
        <div className="flex flex-col gap-3">
          {fields.map((field) => (
            <ReviewFieldCard
              key={field.id}
              field={field}
              busy={busyFieldId === field.id}
              onVerify={(action, value) => void handleVerify(field.id, action, value)}
            />
          ))}
        </div>
      )}
    </QuestionShell>
  )
}
