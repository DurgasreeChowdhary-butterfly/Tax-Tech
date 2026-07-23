import { useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import { humanizeLabel } from '../../utils/format'
import type { ReviewFieldRead, VerificationAction } from '../../types/api'

type ReviewStatus = 'unresolved' | 'verified' | 'edited' | 'pending'

function statusFor(field: ReviewFieldRead): ReviewStatus {
  if (!field.is_supported) return 'unresolved'
  if (!field.current_verification) return 'pending'
  return field.current_verification.action === 'CORRECT' ? 'edited' : 'verified'
}

const STATUS_LABEL: Record<ReviewStatus, string> = {
  unresolved: 'Not reviewable here',
  verified: 'Verified',
  edited: 'Edited',
  pending: 'Pending review',
}

const STATUS_TONE: Record<ReviewStatus, 'neutral' | 'positive' | 'warning' | 'info'> = {
  unresolved: 'neutral',
  verified: 'positive',
  edited: 'info',
  pending: 'warning',
}

interface ReviewFieldCardProps {
  field: ReviewFieldRead
  busy: boolean
  onVerify: (action: VerificationAction, value?: string) => void
}

export function ReviewFieldCard({ field, busy, onVerify }: ReviewFieldCardProps) {
  const [editing, setEditing] = useState(false)
  const [draftValue, setDraftValue] = useState('')
  const status = statusFor(field)

  const currentDisplayValue = field.current_verification ? field.current_verification.verified_value : field.raw_value

  function startEditing() {
    setDraftValue(String(currentDisplayValue ?? ''))
    setEditing(true)
  }

  function handleSave() {
    onVerify('CORRECT', draftValue)
    setEditing(false)
  }

  return (
    <div
      data-testid={`review-field-${field.field_name}`}
      className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4 dark:border-gray-800"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium text-gray-900 dark:text-gray-100">{humanizeLabel(field.field_name)}</p>
        <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>
      </div>

      {!editing && (
        <p className="text-base text-gray-800 dark:text-gray-200">{String(currentDisplayValue ?? '—')}</p>
      )}

      <p className="text-xs text-gray-500 dark:text-gray-400">
        Extracted value: {String(field.raw_value ?? '—')} · Confidence: {Math.round(field.confidence * 100)}%
      </p>

      {status === 'unresolved' && (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          This field can&apos;t be confirmed or corrected in this app.
        </p>
      )}

      {field.is_supported && !editing && (
        <div className="mt-1 flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => onVerify('CONFIRM')}
            className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Accept
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={startEditing}
            className="flex-1 rounded-lg bg-gray-100 px-3 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-800 dark:text-gray-100"
          >
            Edit
          </button>
        </div>
      )}

      {field.is_supported && editing && (
        <div className="mt-1 flex flex-col gap-2">
          <label className="sr-only" htmlFor={`field-${field.id}-correction`}>
            Corrected value for {humanizeLabel(field.field_name)}
          </label>
          <input
            id={`field-${field.id}-correction`}
            type="text"
            value={draftValue}
            onChange={(e) => setDraftValue(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy || draftValue.trim().length === 0}
              onClick={handleSave}
              className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Save correction
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setEditing(false)}
              className="flex-1 rounded-lg bg-gray-100 px-3 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
