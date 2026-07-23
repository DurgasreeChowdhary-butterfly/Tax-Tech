import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function DashboardPage() {
  const { user } = useAuth()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Welcome{user ? `, ${user.email}` : ''}</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">This is your ITR Filing dashboard.</p>
      </div>
      <Link
        to="/filing-sessions"
        className="rounded-lg border border-gray-200 p-4 text-left hover:border-blue-400 dark:border-gray-800"
      >
        <p className="font-medium text-gray-900 dark:text-gray-100">Filing sessions</p>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">Continue an in-progress filing.</p>
      </Link>
    </div>
  )
}
