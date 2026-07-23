import { apiRequest } from './client'
import type { SupportedCaseResultRead } from '../types/api'

/** The Supported Case Validator's outcome — computed entirely server-side
 * (backend/app/engines/tax/supported_case.py). The frontend only renders
 * `outcome`/`reasons`; it never re-derives support status itself. */
export const supportedCaseApi = {
  get: (filingSessionId: string): Promise<SupportedCaseResultRead> =>
    apiRequest(`/filing-sessions/${filingSessionId}/supported-case`),
}
