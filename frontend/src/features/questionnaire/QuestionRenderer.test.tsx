import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { QuestionRenderer } from './QuestionRenderer'
import { documentApi } from '../../api/documents'
import type { QuestionRead } from '../../types/api'

// ReviewCardQuestion (REVIEW_CARD) fetches the document list on mount; this
// file only asserts dispatch, so give it a promise that never resolves
// rather than exercising a real network call. Its own loading/data/verify
// behavior is covered by ReviewCardQuestion.test.tsx.
vi.mock('../../api/documents', () => ({
  documentApi: { list: vi.fn(), get: vi.fn(), upload: vi.fn() },
}))
const mockedDocumentApi = vi.mocked(documentApi)

function makeQuestion(overrides: Partial<QuestionRead>): QuestionRead {
  return {
    id: 'q1',
    key: 'test_question',
    order_index: 1,
    question_type: 'TEXT',
    prompt: 'Test prompt',
    is_required: true,
    options: [],
    ...overrides,
  }
}

describe('QuestionRenderer', () => {
  it('renders BOOLEAN as a Yes/No choice and submits a real boolean', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QuestionRenderer question={makeQuestion({ question_type: 'BOOLEAN' })} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    await user.click(screen.getByRole('radio', { name: 'Yes' }))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith(true)
  })

  it('renders SINGLE_CHOICE options and submits the selected option value', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    const question = makeQuestion({
      question_type: 'SINGLE_CHOICE',
      options: [
        { value: 'GUIDED', label: 'Guided walkthrough', order_index: 1 },
        { value: 'QUICK', label: 'Quick estimate', order_index: 2 },
      ],
    })
    render(<QuestionRenderer question={question} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    await user.click(screen.getByRole('radio', { name: 'Quick estimate' }))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith('QUICK')
  })

  it('renders MULTI_CHOICE checkboxes and submits a list of selected values', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    const question = makeQuestion({
      question_type: 'MULTI_CHOICE',
      options: [
        { value: 'A', label: 'Option A', order_index: 1 },
        { value: 'B', label: 'Option B', order_index: 2 },
      ],
    })
    render(<QuestionRenderer question={question} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    await user.click(screen.getByLabelText('Option A'))
    await user.click(screen.getByLabelText('Option B'))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith(['A', 'B'])
  })

  it('renders TEXT as a textarea and submits the typed string', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QuestionRenderer question={makeQuestion({ question_type: 'TEXT' })} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    await user.type(screen.getByRole('textbox'), 'hello there')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith('hello there')
  })

  it('disables Continue for a required TEXT question until non-empty', () => {
    render(<QuestionRenderer question={makeQuestion({ question_type: 'TEXT', is_required: true })} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('renders NUMBER as a numeric input and submits an integer, not a string', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QuestionRenderer question={makeQuestion({ question_type: 'NUMBER' })} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    const input = screen.getByRole('spinbutton')
    await user.type(input, '3')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith(3)
    expect(onSubmit.mock.calls[0][0]).not.toBe('3')
  })

  it('renders CURRENCY as a decimal-friendly input and submits a decimal STRING', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QuestionRenderer question={makeQuestion({ question_type: 'CURRENCY' })} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    await user.type(screen.getByRole('textbox'), '1234.56')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith('1234.56')
  })

  it('keeps Continue disabled for CURRENCY input that does not look like an amount', async () => {
    const user = userEvent.setup()
    render(<QuestionRenderer question={makeQuestion({ question_type: 'CURRENCY' })} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)

    await user.type(screen.getByRole('textbox'), 'not-a-number')
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('renders DATE as a native date input and submits an ISO date string', async () => {
    const onSubmit = vi.fn()
    render(<QuestionRenderer question={makeQuestion({ question_type: 'DATE' })} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    const input = document.getElementById('date-answer') as HTMLInputElement
    const user = userEvent.setup()
    await user.type(input, '2026-04-15')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith('2026-04-15')
  })

  it('renders INFORMATION with no answer input and submits null on Continue', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QuestionRenderer question={makeQuestion({ question_type: 'INFORMATION' })} submitting={false} onSubmit={onSubmit} filingSessionId="fs-1" />)

    expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onSubmit).toHaveBeenCalledWith(null)
  })

  it('renders DOCUMENT_UPLOAD as a real file-upload step, not a placeholder', () => {
    render(<QuestionRenderer question={makeQuestion({ question_type: 'DOCUMENT_UPLOAD' })} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    expect(document.getElementById('document-upload-input')).toBeInTheDocument()
  })

  it('renders REVIEW_CARD as a real review step, not a placeholder', () => {
    mockedDocumentApi.list.mockReturnValue(new Promise(() => {})) // never resolves
    render(<QuestionRenderer question={makeQuestion({ question_type: 'REVIEW_CARD' })} submitting={false} onSubmit={vi.fn()} filingSessionId="fs-1" />)
    // Dedicated behavior (loading -> fields -> verify) is covered by
    // ReviewCardQuestion.test.tsx; this only asserts real dispatch happened.
    expect(screen.getAllByRole('status', { name: 'Loading' }).length).toBeGreaterThan(0)
  })

  it('shows a loading state on the Continue button while submitting', () => {
    render(<QuestionRenderer question={makeQuestion({ question_type: 'INFORMATION' })} submitting onSubmit={vi.fn()} filingSessionId="fs-1" />)
    expect(screen.getByRole('button', { name: /please wait/i })).toBeInTheDocument()
  })
})
