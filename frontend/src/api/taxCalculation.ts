import { apiRequest } from './client'
import type { TaxCalculationResponse, TaxRegime } from '../types/api'

/** Every figure here is computed by the deterministic backend tax engine
 * (backend/app/engines/tax/calculation.py) — this module never calculates,
 * compares, or rounds a tax figure itself. */
export const taxCalculationApi = {
  getCalculation: (filingSessionId: string, regime: TaxRegime): Promise<TaxCalculationResponse> =>
    apiRequest(`/filing-sessions/${filingSessionId}/calculations/${regime}`),
}
