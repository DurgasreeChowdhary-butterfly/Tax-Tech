import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentUploadQuestion } from './DocumentUploadQuestion'
import { documentApi } from '../../api/documents'
import { extractionApi } from '../../api/extraction'
import { ApiError } from '../../api/client'
import type { QuestionRead } from '../../types/api'

vi.mock('../../api/documents', () => ({ documentApi: { upload: vi.fn(), list: vi.fn(), get: vi.fn() } }))
vi.mock('../../api/extraction', () => ({
  extractionApi: { startExtraction: vi.fn(), getJob: vi.fn(), getReviewFields: vi.fn(), verifyField: vi.fn() },
}))

const mockedDocumentApi = vi.mocked(documentApi)
const mockedExtractionApi = vi.mocked(extractionApi)

const question: QuestionRead = {
  id: 'q-upload',
  key: 'form16_upload',
  order_index: 1,
  question_type: 'DOCUMENT_UPLOAD',
  prompt: 'Upload your Form 16',
  is_required: true,
  options: [],
}

function selectFile(input: HTMLElement) {
  const file = new File(['%PDF-1.4 fake'], 'form16.pdf', { type: 'application/pdf' })
  return userEvent.upload(input, file)
}

describe('DocumentUploadQuestion', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('uploads the file, starts extraction, and enables Continue once processing completes', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    mockedDocumentApi.upload.mockResolvedValue({
      document: { id: 'doc-1', original_filename: 'form16.pdf', content_type: 'application/pdf', size_bytes: 10, status: 'UPLOADED', created_at: '2026-01-01T00:00:00Z', deleted_at: null },
      is_duplicate: false,
    })
    mockedExtractionApi.startExtraction.mockResolvedValue({
      id: 'job-1', tax_document_id: 'doc-1', provider: 'MOCK', status: 'COMPLETED', error_code: null, error_message: null,
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    })

    render(<DocumentUploadQuestion question={question} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    await selectFile(screen.getByLabelText(question.prompt))
    await user.click(screen.getByRole('button', { name: 'Upload document' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled())
    expect(mockedDocumentApi.upload).toHaveBeenCalledWith('fs-1', expect.any(File))
    expect(mockedExtractionApi.startExtraction).toHaveBeenCalledWith('fs-1', 'doc-1')

    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(onSubmit).toHaveBeenCalledWith({ document_id: 'doc-1' })
  })

  it('polls the job when extraction is not yet finished, then finishes on COMPLETED', async () => {
    const user = userEvent.setup()
    mockedDocumentApi.upload.mockResolvedValue({
      document: { id: 'doc-1', original_filename: 'form16.pdf', content_type: 'application/pdf', size_bytes: 10, status: 'UPLOADED', created_at: '2026-01-01T00:00:00Z', deleted_at: null },
      is_duplicate: false,
    })
    mockedExtractionApi.startExtraction.mockResolvedValue({
      id: 'job-1', tax_document_id: 'doc-1', provider: 'MOCK', status: 'RUNNING', error_code: null, error_message: null,
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    })
    mockedExtractionApi.getJob.mockResolvedValue({
      id: 'job-1', tax_document_id: 'doc-1', provider: 'MOCK', status: 'COMPLETED', error_code: null, error_message: null,
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    })

    render(<DocumentUploadQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    await selectFile(screen.getByLabelText(question.prompt))
    await user.click(screen.getByRole('button', { name: 'Upload document' }))

    await waitFor(() => expect(mockedExtractionApi.getJob).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled())
  })

  it('shows a retryable error state when upload fails', async () => {
    const user = userEvent.setup()
    mockedDocumentApi.upload.mockRejectedValue(new ApiError(403, 'Required consent has not been accepted'))

    render(<DocumentUploadQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    await selectFile(screen.getByLabelText(question.prompt))
    await user.click(screen.getByRole('button', { name: 'Upload document' }))

    expect(await screen.findByText('Required consent has not been accepted')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('shows the backend failure message when extraction itself fails', async () => {
    const user = userEvent.setup()
    mockedDocumentApi.upload.mockResolvedValue({
      document: { id: 'doc-1', original_filename: 'form16.pdf', content_type: 'application/pdf', size_bytes: 10, status: 'UPLOADED', created_at: '2026-01-01T00:00:00Z', deleted_at: null },
      is_duplicate: false,
    })
    mockedExtractionApi.startExtraction.mockResolvedValue({
      id: 'job-1', tax_document_id: 'doc-1', provider: 'MOCK', status: 'FAILED', error_code: 'PROVIDER_ERROR',
      error_message: 'We could not process this document. Please try uploading it again.',
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    })

    render(<DocumentUploadQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    await selectFile(screen.getByLabelText(question.prompt))
    await user.click(screen.getByRole('button', { name: 'Upload document' }))

    expect(await screen.findByText('We could not process this document. Please try uploading it again.')).toBeInTheDocument()
  })

  it('disables the upload button until a file is chosen', () => {
    render(<DocumentUploadQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    expect(screen.getByRole('button', { name: 'Upload document' })).toBeDisabled()
  })
})
