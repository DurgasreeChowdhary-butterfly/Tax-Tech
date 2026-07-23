import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { TextField } from '../../components/ui/TextField'
import { EmptyState } from '../../components/ui/EmptyState'

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/**
 * Backend Phases 1–11 expose no `/api/v1/filing-sessions` list-or-create
 * endpoint — filing_sessions are currently created only at the repository
 * layer (see backend/app/repositories/filing_session.py), by design for
 * this phase (docs/IMPLEMENTATION_PLAN.md Phase 2: "No auth yet — internal
 * service-level creation only"). Phase 12 must not invent a backend
 * endpoint to make this page prettier (CLAUDE.md: frontend consumes
 * existing APIs only). Until that API exists, this page is honest about
 * it: it lets you jump straight to a known filing session's questionnaire
 * (e.g. one created via the backend seed script — see
 * backend/scripts/seed_dev_data.py) rather than pretending to list or
 * create sessions it has no way to fetch.
 */
export function FilingSessionsPage() {
  const navigate = useNavigate()
  const [filingSessionId, setFilingSessionId] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = filingSessionId.trim()
    if (!UUID_PATTERN.test(trimmed)) {
      setError('Enter a valid filing session ID.')
      return
    }
    setError(null)
    void navigate(`/filing-sessions/${trimmed}/questionnaire`)
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Filing sessions</h1>
      <EmptyState
        title="No filing session list available yet"
        description="Session listing/creation isn't exposed by the backend API in this phase. If you already have a filing session ID, open its questionnaire directly below."
      />
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          label="Filing session ID"
          placeholder="00000000-0000-0000-0000-000000000000"
          value={filingSessionId}
          onChange={(e) => setFilingSessionId(e.target.value)}
          error={error}
        />
        <Button type="submit" className="sm:max-w-xs">
          Open questionnaire
        </Button>
      </form>
    </div>
  )
}
