import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ReviewCardQuestion } from './ReviewCardQuestion'
import { documentApi } from '../../api/documents'
import { extractionApi } from '../../api/extraction'
import { ApiError } from '../../api/client'
import type { DocumentRead, QuestionRead, ReviewFieldRead } from '../../types/api'

vi.mock('../../api/documents', () => ({ documentApi: { list: vi.fn(), get: vi.fn(), upload: vi.fn() } }))
vi.mock('../../api/extraction', () => ({
  extractionApi: { startExtraction: vi.fn(), getJob: vi.fn(), getReviewFields: vi.fn(), verifyField: vi.fn() },
}))

const mockedDocumentApi = vi.mocked(documentApi)
const mockedExtractionApi = vi.mocked(extractionApi)

const question: QuestionRead = {
  id: 'q-review',
  key: 'review_extracted_details',
  order_index: 2,
  question_type: 'REVIEW_CARD',
  prompt: 'Review the details we found',
  is_required: true,
  options: [],
}

function doc(overrides: Partial<DocumentRead> = {}): DocumentRead {
  return {
    id: 'doc-1',
    original_filename: 'form16.pdf',
    content_type: 'application/pdf',
    size_bytes: 10,
    status: 'UPLOADED',
    created_at: '2026-01-01T00:00:00Z',
    deleted_at: null,
    ...overrides,
  }
}

function field(overrides: Partial<ReviewFieldRead>): ReviewFieldRead {
  return {
    id: 'field-1',
    field_name: 'gross_salary',
    raw_value: '1200000.00',
    confidence: 0.85,
    is_supported: true,
    current_verification: null,
    ...overrides,
  }
}

describe('ReviewCardQuestion', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a skeleton while loading, then the extracted fields grouped by review status', async () => {
    mockedDocumentApi.list.mockResolvedValue({ documents: [doc()] })
    mockedExtractionApi.getReviewFields.mockResolvedValue([
      field({ id: 'f1', field_name: 'gross_salary', current_verification: null }),
      field({
        id: 'f2',
        field_name: 'employer_name',
        raw_value: 'MOCK EMPLOYER PVT LTD',
        current_verification: { id: 'v1', action: 'CONFIRM', verified_value: 'MOCK EMPLOYER PVT LTD', is_current: true, created_at: '2026-01-01T00:00:00Z' },
      }),
      field({
        id: 'f3',
        field_name: 'tds_deducted',
        raw_value: '95000.00',
        current_verification: { id: 'v2', action: 'CORRECT', verified_value: '90000.00', is_current: true, created_at: '2026-01-01T00:00:00Z' },
      }),
      field({ id: 'f4', field_name: 'pan', raw_value: 'AAAPZ9999Z', is_supported: false }),
    ])

    render(<ReviewCardQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)

    expect(screen.getAllByRole('status', { name: 'Loading' }).length).toBeGreaterThan(0)

    expect(await screen.findByText('Gross salary')).toBeInTheDocument()
    expect(screen.getByText('Pending review')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(screen.getByText('Edited')).toBeInTheDocument()
    expect(screen.getByText('Not reviewable here')).toBeInTheDocument()
    // The edited field shows the corrected value, not the original raw one.
    expect(screen.getByText('90000.00')).toBeInTheDocument()
  })

  it('accepts a field by submitting CONFIRM and refetches the authoritative list', async () => {
    const user = userEvent.setup()
    mockedDocumentApi.list.mockResolvedValue({ documents: [doc()] })
    mockedExtractionApi.getReviewFields
      .mockResolvedValueOnce([field({ id: 'f1', current_verification: null })])
      .mockResolvedValueOnce([
        field({
          id: 'f1',
          current_verification: { id: 'v1', action: 'CONFIRM', verified_value: '1200000.00', is_current: true, created_at: '2026-01-01T00:00:00Z' },
        }),
      ])
    mockedExtractionApi.verifyField.mockResolvedValue({
      verification: { id: 'v1', action: 'CONFIRM', verified_value: '1200000.00', is_current: true, created_at: '2026-01-01T00:00:00Z' },
    })

    render(<ReviewCardQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    await screen.findByText('Gross salary')

    await user.click(screen.getByRole('button', { name: 'Accept' }))

    expect(mockedExtractionApi.verifyField).toHaveBeenCalledWith('fs-1', 'doc-1', 'f1', { action: 'CONFIRM', value: undefined })
    await waitFor(() => expect(screen.getByText('Verified')).toBeInTheDocument())
    expect(mockedExtractionApi.getReviewFields).toHaveBeenCalledTimes(2)
  })

  it('edits a field by submitting CORRECT with the typed value', async () => {
    const user = userEvent.setup()
    mockedDocumentApi.list.mockResolvedValue({ documents: [doc()] })
    mockedExtractionApi.getReviewFields
      .mockResolvedValueOnce([field({ id: 'f1', raw_value: '1200000.00', current_verification: null })])
      .mockResolvedValueOnce([
        field({
          id: 'f1',
          raw_value: '1200000.00',
          current_verification: { id: 'v1', action: 'CORRECT', verified_value: '1250000.00', is_current: true, created_at: '2026-01-01T00:00:00Z' },
        }),
      ])
    mockedExtractionApi.verifyField.mockResolvedValue({
      verification: { id: 'v1', action: 'CORRECT', verified_value: '1250000.00', is_current: true, created_at: '2026-01-01T00:00:00Z' },
    })

    render(<ReviewCardQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    await screen.findByText('Gross salary')

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    const input = screen.getByRole('textbox')
    await user.clear(input)
    await user.type(input, '1250000.00')
    await user.click(screen.getByRole('button', { name: 'Save correction' }))

    expect(mockedExtractionApi.verifyField).toHaveBeenCalledWith('fs-1', 'doc-1', 'f1', { action: 'CORRECT', value: '1250000.00' })
    await waitFor(() => expect(screen.getByText('1250000.00')).toBeInTheDocument())
  })

  it('shows a graceful empty state when there is no document to review yet', async () => {
    mockedDocumentApi.list.mockResolvedValue({ documents: [] })

    render(<ReviewCardQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)

    expect(await screen.findByText('No documents to review yet')).toBeInTheDocument()
  })

  it('shows a retryable error state when loading fails', async () => {
    mockedDocumentApi.list.mockRejectedValue(new ApiError(500, 'Something went wrong'))

    render(<ReviewCardQuestion question={question} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })
})
