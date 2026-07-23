import type { QuestionnaireProgressRead } from '../../types/api'

export function ProgressBar({ progress }: { progress: QuestionnaireProgressRead }) {
  const percent = progress.total_questions === 0 ? 0 : Math.round((progress.answered_questions / progress.total_questions) * 100)

  return (
    <div className="mb-6">
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-800"
      >
        <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
        {progress.answered_questions} of {progress.total_questions} answered
      </p>
    </div>
  )
}
