import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { supportedCaseApi } from '../../api/supportedCase'
import { taxCalculationApi } from '../../api/taxCalculation'
import { ApiError } from '../../api/client'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageSkeleton } from '../../components/ui/Skeleton'
import type { SupportedCaseResultRead, TaxCalculationResponse, TaxRegime } from '../../types/api'
import { CalculationBreakdown } from './CalculationBreakdown'
import { SupportedCaseBlocked } from './SupportedCaseBlocked'

const REGIME_LABEL: Record<TaxRegime, string> = { OLD: 'Old regime', NEW: 'New regime' }

function isTaxRegime(value: string | undefined): value is TaxRegime {
  return value === 'OLD' || value === 'NEW'
}

/**
 * Final tax summary screen for one regime — the last step of the guided
 * journey (docs/PRODUCT_SCOPE.md). Displays exactly what
 * GET /filing-sessions/{id}/calculations/{regime} returned; computes nothing.
 */
export function TaxSummaryPage() {
  const { filingSessionId, regime } = useParams<{ filingSessionId: string; regime: string }>()
  const [supportedCase, setSupportedCase] = useState<SupportedCaseResultRead | null>(null)
  const [response, setResponse] = useState<TaxCalculationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    if (!filingSessionId || !isTaxRegime(regime)) return
    const requestId = ++requestIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await supportedCaseApi.get(filingSessionId)
      if (requestIdRef.current !== requestId) return
      setSupportedCase(result)

      if (result.outcome === 'SUPPORTED') {
        const calculationResponse = await taxCalculationApi.getCalculation(filingSessionId, regime)
        if (requestIdRef.current !== requestId) return
        setResponse(calculationResponse)
      }
    } catch (err) {
      if (requestIdRef.current === requestId) {
        setError(err instanceof ApiError ? err.message : 'Could not load this tax summary.')
      }
    } finally {
      if (requestIdRef.current === requestId) {
        setLoading(false)
      }
    }
  }, [filingSessionId, regime])

  useEffect(() => {
    void load()
    return () => {
      requestIdRef.current += 1
    }
  }, [load])

  if (!filingSessionId || !isTaxRegime(regime)) {
    return <ErrorState message="No valid tax regime was specified." />
  }
  if (loading) {
    return <PageSkeleton />
  }
  if (error) {
    return <ErrorState message={error} onRetry={() => void load()} />
  }
  if (supportedCase && supportedCase.outcome !== 'SUPPORTED') {
    return <SupportedCaseBlocked outcome={supportedCase.outcome} reasons={supportedCase.reasons} />
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Tax summary — {REGIME_LABEL[regime]}</h1>
      {response && <CalculationBreakdown calculation={response.calculation} lineItems={response.line_items} />}
    </div>
  )
}
