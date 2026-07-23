import { apiRequest } from './client'
import type { DocumentListResponse, DocumentRead, DocumentUploadResponse } from '../types/api'

export const documentApi = {
  upload: (filingSessionId: string, file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    return apiRequest(`/filing-sessions/${filingSessionId}/documents`, { method: 'POST', body: formData })
  },

  list: (filingSessionId: string): Promise<DocumentListResponse> =>
    apiRequest(`/filing-sessions/${filingSessionId}/documents`),

  get: (filingSessionId: string, documentId: string): Promise<DocumentRead> =>
    apiRequest(`/filing-sessions/${filingSessionId}/documents/${documentId}`),
}
