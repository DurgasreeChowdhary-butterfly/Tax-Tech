import { apiRequest } from './client'
import type { AnswerSubmitRequest, CurrentQuestionResponse, QuestionnaireProgressRead, SubmitAnswerResponse } from '../types/api'

/** Every call here just forwards to the backend's own routing/decision
 * engine (backend/app/api/v1/questionnaire.py) — nothing in this module
 * decides what the next question is or whether the questionnaire is
 * complete; it only reports back exactly what the backend said. */
export const questionnaireApi = {
  getCurrent: (filingSessionId: string): Promise<CurrentQuestionResponse> =>
    apiRequest(`/filing-sessions/${filingSessionId}/questionnaire/current`),

  submitAnswer: (filingSessionId: string, body: AnswerSubmitRequest): Promise<SubmitAnswerResponse> =>
    apiRequest(`/filing-sessions/${filingSessionId}/questionnaire/answers`, { method: 'POST', body }),

  getProgress: (filingSessionId: string): Promise<QuestionnaireProgressRead> =>
    apiRequest(`/filing-sessions/${filingSessionId}/questionnaire/progress`),
}
