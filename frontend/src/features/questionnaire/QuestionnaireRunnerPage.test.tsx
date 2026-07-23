import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QuestionnaireRunnerPage } from './QuestionnaireRunnerPage'
import { questionnaireApi } from '../../api/questionnaire'
import { ApiError } from '../../api/client'
import type { QuestionRead } from '../../types/api'

vi.mock('../../api/questionnaire', () => ({
  questionnaireApi: {
    getCurrent: vi.fn(),
    submitAnswer: vi.fn(),
    getProgress: vi.fn(),
  },
}))

const mockedApi = vi.mocked(questionnaireApi)

const questionOne: QuestionRead = {
  id: 'q1',
  key: 'has_other_income',
  order_index: 1,
  question_type: 'BOOLEAN',
  prompt: 'Do you have any other income sources?',
  is_required: true,
  options: [],
}

const questionTwo: QuestionRead = {
  id: 'q2',
  key: 'filing_intent',
  order_index: 3,
  question_type: 'SINGLE_CHOICE',
  prompt: 'How would you like to proceed?',
  is_required: true,
  options: [
    { value: 'GUIDED', label: 'Guided walkthrough', order_index: 1 },
    { value: 'QUICK', label: 'Quick estimate', order_index: 2 },
  ],
}

const FILING_SESSION_ID = '11111111-1111-1111-1111-111111111111'

function renderRunner() {
  return render(
    <MemoryRouter initialEntries={[`/filing-sessions/${FILING_SESSION_ID}/questionnaire`]}>
      <Routes>
        <Route path="/filing-sessions/:filingSessionId/questionnaire" element={<QuestionnaireRunnerPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('QuestionnaireRunnerPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders whatever question the backend returns, with no local routing decision', async () => {
    mockedApi.getCurrent.mockResolvedValue({ question: questionOne, is_complete: false })
    mockedApi.getProgress.mockResolvedValue({ total_questions: 5, answered_questions: 0, is_complete: false })

    renderRunner()

    expect(await screen.findByText(questionOne.prompt)).toBeInTheDocument()
    expect(mockedApi.getCurrent).toHaveBeenCalledWith(FILING_SESSION_ID)
    expect(screen.getByText('0 of 5 answered')).toBeInTheDocument()
  })

  it('advances to whatever next_question the submit-answer response contains, verbatim', async () => {
    mockedApi.getCurrent.mockResolvedValue({ question: questionOne, is_complete: false })
    mockedApi.getProgress
      .mockResolvedValueOnce({ total_questions: 5, answered_questions: 0, is_complete: false })
      .mockResolvedValueOnce({ total_questions: 5, answered_questions: 1, is_complete: false })
    mockedApi.submitAnswer.mockResolvedValue({
      answer: { id: 'a1', filing_session_id: FILING_SESSION_ID, question_id: 'q1', value: true, is_current: true, created_at: '2026-01-01T00:00:00Z' },
      next_question: questionTwo,
      is_complete: false,
    })

    const user = userEvent.setup()
    renderRunner()
    await screen.findByText(questionOne.prompt)

    await user.click(screen.getByRole('radio', { name: 'Yes' }))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText(questionTwo.prompt)).toBeInTheDocument()
    expect(mockedApi.submitAnswer).toHaveBeenCalledWith(FILING_SESSION_ID, { question_id: 'q1', value: true })
    await waitFor(() => expect(screen.getByText('1 of 5 answered')).toBeInTheDocument())
  })

  it('shows a completion screen when the backend reports is_complete, without the runner deciding that itself', async () => {
    mockedApi.getCurrent.mockResolvedValue({ question: null, is_complete: true })
    mockedApi.getProgress.mockResolvedValue({ total_questions: 5, answered_questions: 5, is_complete: true })

    renderRunner()

    expect(await screen.findByText("You're all caught up")).toBeInTheDocument()
  })

  it('shows a retry-able error state when the initial load fails', async () => {
    mockedApi.getCurrent.mockRejectedValue(new ApiError(404, 'Filing session not found'))
    mockedApi.getProgress.mockRejectedValue(new ApiError(404, 'Filing session not found'))

    renderRunner()

    expect(await screen.findByRole('alert')).toHaveTextContent('Filing session not found')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows a submit error and stays on the same question if the backend rejects the answer', async () => {
    mockedApi.getCurrent.mockResolvedValue({ question: questionOne, is_complete: false })
    mockedApi.getProgress.mockResolvedValue({ total_questions: 5, answered_questions: 0, is_complete: false })
    mockedApi.submitAnswer.mockRejectedValue(new ApiError(400, 'expected a boolean value'))

    const user = userEvent.setup()
    renderRunner()
    await screen.findByText(questionOne.prompt)

    await user.click(screen.getByRole('radio', { name: 'Yes' }))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('expected a boolean value')).toBeInTheDocument()
    expect(screen.getByText(questionOne.prompt)).toBeInTheDocument() // still on q1
  })
})
