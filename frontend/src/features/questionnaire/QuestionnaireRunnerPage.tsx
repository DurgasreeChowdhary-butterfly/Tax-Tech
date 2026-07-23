import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { questionnaireApi } from '../../api/questionnaire'
import { ApiError } from '../../api/client'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageSkeleton } from '../../components/ui/Skeleton'
import type { QuestionnaireProgressRead, QuestionRead } from '../../types/api'
import { QuestionRenderer } from './QuestionRenderer'
import { ProgressBar } from './ProgressBar'

interface RunnerState {
  question: QuestionRead | null
  isComplete: boolean
}

/**
 * The Phase 12 questionnaire runner "shell": entirely backend-driven. It
 * never decides what the next question is, never evaluates a routing rule,
 * and never computes progress itself — every one of those comes straight
 * from a backend response (GET .../current, POST .../answers, GET
 * .../progress) and is rendered as-is. Its own state is limited to loading/
 * submitting/error UI flags plus whatever the backend last told it.
 */
export function QuestionnaireRunnerPage() {
  const { filingSessionId } = useParams<{ filingSessionId: string }>()
  const [state, setState] = useState<RunnerState | null>(null)
  const [progress, setProgress] = useState<QuestionnaireProgressRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Guards against an out-of-order response: if filingSessionId changes (or
  // the component unmounts) while a load() from a previous session is still
  // in flight, its result must never overwrite state for the session the
  // user is now looking at.
  const loadRequestIdRef = useRef(0)

  const load = useCallback(async () => {
    if (!filingSessionId) return
    const requestId = ++loadRequestIdRef.current
    setLoading(true)
    setLoadError(null)
    try {
      const [current, progressResult] = await Promise.all([
        questionnaireApi.getCurrent(filingSessionId),
        questionnaireApi.getProgress(filingSessionId),
      ])
      if (loadRequestIdRef.current !== requestId) return
      setState({ question: current.question, isComplete: current.is_complete })
      setProgress(progressResult)
    } catch (error) {
      if (loadRequestIdRef.current === requestId) {
        setLoadError(error instanceof ApiError ? error.message : 'Could not load this filing session.')
      }
    } finally {
      if (loadRequestIdRef.current === requestId) {
        setLoading(false)
      }
    }
  }, [filingSessionId])

  useEffect(() => {
    void load()
    return () => {
      loadRequestIdRef.current += 1
    }
  }, [load])

  async function handleAnswer(value: unknown) {
    if (!filingSessionId || !state?.question) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const result = await questionnaireApi.submitAnswer(filingSessionId, {
        question_id: state.question.id,
        value,
      })
      setState({ question: result.next_question, isComplete: result.is_complete })
      const progressResult = await questionnaireApi.getProgress(filingSessionId)
      setProgress(progressResult)
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : 'Could not submit that answer. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!filingSessionId) {
    return <ErrorState message="No filing session was specified." />
  }

  if (loading) {
    return <PageSkeleton />
  }

  if (loadError) {
    return <ErrorState message={loadError} onRetry={() => void load()} />
  }

  if (!state || state.isComplete || !state.question) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-6 text-center">
        <p className="text-xl font-semibold text-gray-900 dark:text-gray-100">You're all caught up</p>
        <p className="text-sm text-gray-600 dark:text-gray-300">There are no more questions to answer right now.</p>
        <Link
          to={`/filing-sessions/${filingSessionId}/regime-comparison`}
          className="text-sm font-medium text-blue-700 dark:text-blue-400"
        >
          View regime comparison
        </Link>
        <Link to="/filing-sessions" className="text-sm font-medium text-gray-600 dark:text-gray-300">
          Back to filing sessions
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-md">
      {progress && <ProgressBar progress={progress} />}
      {submitError && (
        <p role="alert" className="mb-4 text-sm text-red-600 dark:text-red-400">
          {submitError}
        </p>
      )}
      <QuestionRenderer
        key={state.question.id}
        question={state.question}
        submitting={submitting}
        onSubmit={handleAnswer}
        filingSessionId={filingSessionId}
      />
    </div>
  )
}
