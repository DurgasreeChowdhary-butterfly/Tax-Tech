import { useRef, useState } from 'react'
import { documentApi } from '../../api/documents'
import { extractionApi } from '../../api/extraction'
import { ApiError } from '../../api/client'
import { QuestionShell } from '../questionnaire/QuestionShell'
import type { QuestionComponentProps } from '../questionnaire/questions/types'
import type { DocumentProcessingJobRead } from '../../types/api'

type Phase = 'PICK' | 'UPLOADING' | 'EXTRACTING' | 'DONE' | 'ERROR'

const ACCEPTED_FILE_TYPES = '.pdf,.jpg,.jpeg,.png'
const POLL_INTERVAL_MS = 500
const MAX_POLL_ATTEMPTS = 10

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * DOCUMENT_UPLOAD question: upload a file, then kick off extraction and wait
 * for it to finish (backend/app/api/v1/document.py, extraction.py). This
 * component never reads or interprets the document's contents itself — it
 * only uploads bytes and polls a job status the backend already computed.
 * Continue submits the document_id as this question's answer so it's
 * recorded in the immutable answer history; the next (REVIEW_CARD) question
 * discovers which document to review from the filing session's document
 * list, not from this answer value.
 */
export function DocumentUploadQuestion({ question, submitting, onSubmit, filingSessionId }: QuestionComponentProps) {
  const [phase, setPhase] = useState<Phase>('PICK')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const attemptIdRef = useRef(0)

  async function waitForExtraction(documentIdForJob: string, job: DocumentProcessingJobRead, attemptId: number) {
    let current = job
    let attempts = 0
    while ((current.status === 'PENDING' || current.status === 'RUNNING') && attempts < MAX_POLL_ATTEMPTS) {
      await sleep(POLL_INTERVAL_MS)
      if (attemptIdRef.current !== attemptId) return
      current = await extractionApi.getJob(filingSessionId, documentIdForJob, current.id)
      attempts += 1
    }
    if (attemptIdRef.current !== attemptId) return

    if (current.status === 'COMPLETED') {
      setPhase('DONE')
    } else if (current.status === 'FAILED') {
      setPhase('ERROR')
      setErrorMessage(current.error_message ?? 'Document processing failed. Please try again.')
    } else {
      setPhase('ERROR')
      setErrorMessage('This is taking longer than expected. Please try again in a moment.')
    }
  }

  async function handleUpload() {
    if (!selectedFile) return
    const attemptId = ++attemptIdRef.current
    setPhase('UPLOADING')
    setErrorMessage(null)
    try {
      const uploadResult = await documentApi.upload(filingSessionId, selectedFile)
      if (attemptIdRef.current !== attemptId) return
      setDocumentId(uploadResult.document.id)
      setPhase('EXTRACTING')

      const job = await extractionApi.startExtraction(filingSessionId, uploadResult.document.id)
      if (attemptIdRef.current !== attemptId) return
      await waitForExtraction(uploadResult.document.id, job, attemptId)
    } catch (error) {
      if (attemptIdRef.current !== attemptId) return
      setPhase('ERROR')
      setErrorMessage(error instanceof ApiError ? error.message : 'Could not upload this document. Please try again.')
    }
  }

  function handleRetry() {
    attemptIdRef.current += 1
    setPhase('PICK')
    setDocumentId(null)
    setErrorMessage(null)
  }

  const canSubmit = phase === 'DONE' && documentId !== null

  return (
    <QuestionShell
      question={question}
      submitting={submitting}
      canSubmit={canSubmit}
      onSubmit={() => onSubmit({ document_id: documentId })}
    >
      <div className="flex flex-col gap-4">
        {phase === 'PICK' && (
          <>
            <label className="sr-only" htmlFor="document-upload-input">
              {question.prompt}
            </label>
            <input
              id="document-upload-input"
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              className="w-full rounded-lg border border-gray-300 px-3 py-3 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
            />
            <button
              type="button"
              disabled={!selectedFile}
              onClick={() => void handleUpload()}
              className="inline-flex w-full items-center justify-center rounded-lg bg-gray-100 px-4 py-3 text-base font-medium text-gray-900 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-800 dark:text-gray-100 sm:w-auto"
            >
              Upload document
            </button>
          </>
        )}

        {(phase === 'UPLOADING' || phase === 'EXTRACTING') && (
          <p role="status" className="text-sm text-gray-600 dark:text-gray-300">
            {phase === 'UPLOADING' ? 'Uploading document…' : 'Reading document details…'}
          </p>
        )}

        {phase === 'DONE' && (
          <p role="status" className="text-sm text-green-700 dark:text-green-400">
            Document uploaded. Continue to review the details we found.
          </p>
        )}

        {phase === 'ERROR' && (
          <div className="flex flex-col gap-3">
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {errorMessage}
            </p>
            <button
              type="button"
              onClick={handleRetry}
              className="inline-flex w-full items-center justify-center rounded-lg bg-gray-100 px-4 py-3 text-base font-medium text-gray-900 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-100 sm:w-auto"
            >
              Try again
            </button>
          </div>
        )}
      </div>
    </QuestionShell>
  )
}
