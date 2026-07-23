import { apiRequest } from './client'
import type { DocumentProcessingJobRead, ReviewFieldRead, VerifyFieldRequest, VerifyFieldResponse } from '../types/api'

/** Every call here just forwards to the backend's extraction/verification
 * engines (backend/app/api/v1/extraction.py) — confidence scoring, field
 * mapping, and domain-record writes all happen server-side. This module
 * never inspects or judges extraction quality itself. */
export const extractionApi = {
  startExtraction: (filingSessionId: string, documentId: string): Promise<DocumentProcessingJobRead> =>
    apiRequest(`/filing-sessions/${filingSessionId}/documents/${documentId}/extraction`, { method: 'POST' }),

  getJob: (filingSessionId: string, documentId: string, jobId: string): Promise<DocumentProcessingJobRead> =>
    apiRequest(`/filing-sessions/${filingSessionId}/documents/${documentId}/extraction/jobs/${jobId}`),

  getReviewFields: (filingSessionId: string, documentId: string): Promise<ReviewFieldRead[]> =>
    apiRequest(`/filing-sessions/${filingSessionId}/documents/${documentId}/extraction/review`),

  verifyField: (
    filingSessionId: string,
    documentId: string,
    fieldId: string,
    body: VerifyFieldRequest,
  ): Promise<VerifyFieldResponse> =>
    apiRequest(`/filing-sessions/${filingSessionId}/documents/${documentId}/extraction/fields/${fieldId}/verify`, {
      method: 'POST',
      body,
    }),
}
