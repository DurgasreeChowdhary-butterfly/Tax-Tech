import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { supportedCaseApi } from '../../api/supportedCase'
import { taxCalculationApi } from '../../api/taxCalculation'
import { ApiError } from '../../api/client'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageSkeleton } from '../../components/ui/Skeleton'
import type { SupportedCaseResultRead, TaxCalculationRead } from '../../types/api'
import { RegimeSummaryCard } from './RegimeSummaryCard'
import { SupportedCaseBlocked } from './SupportedCaseBlocked'

/**
 * Renders both regimes' already-computed totals side by side
 * (backend/app/api/v1/tax_calculation.py, one GET per regime). This page
 * never compares the two calculations itself and never decides which regime
 * is "better" — that comparison, if the backend ever produces one, would
 * need to arrive as data on the response; today it doesn't, so none is shown.
 */
export function RegimeComparisonPage() {
  const { filingSessionId } = useParams<{ filingSessionId: string }>()
  const [supportedCase, setSupportedCase] = useState<SupportedCaseResultRead | null>(null)
  const [calculations, setCalculations] = useState<{ old: TaxCalculationRead; new: TaxCalculationRead } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    if (!filingSessionId) return
    const requestId = ++requestIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await supportedCaseApi.get(filingSessionId)
      if (requestIdRef.current !== requestId) return
      setSupportedCase(result)

      if (result.outcome === 'SUPPORTED') {
        const [oldResult, newResult] = await Promise.all([
          taxCalculationApi.getCalculation(filingSessionId, 'OLD'),
          taxCalculationApi.getCalculation(filingSessionId, 'NEW'),
        ])
        if (requestIdRef.current !== requestId) return
        setCalculations({ old: oldResult.calculation, new: newResult.calculation })
      }
    } catch (err) {
      if (requestIdRef.current === requestId) {
        setError(err instanceof ApiError ? err.message : 'Could not load the regime comparison.')
      }
    } finally {
      if (requestIdRef.current === requestId) {
        setLoading(false)
      }
    }
  }, [filingSessionId])

  useEffect(() => {
    void load()
    return () => {
      requestIdRef.current += 1
    }
  }, [load])

  if (!filingSessionId) {
    return <ErrorState message="No filing session was specified." />
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
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Regime comparison</h1>
      {calculations && (
        <div className="flex flex-col gap-4 sm:flex-row">
          <RegimeSummaryCard calculation={calculations.old} filingSessionId={filingSessionId} />
          <RegimeSummaryCard calculation={calculations.new} filingSessionId={filingSessionId} />
        </div>
      )}
    </div>
  )
}
