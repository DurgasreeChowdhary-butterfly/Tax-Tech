import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-3xl font-semibold text-gray-900 dark:text-gray-100">404</p>
      <p className="text-gray-600 dark:text-gray-300">This page doesn't exist.</p>
      <Link to="/" className="text-sm font-medium text-blue-700 dark:text-blue-400">
        Back to dashboard
      </Link>
    </div>
  )
}
