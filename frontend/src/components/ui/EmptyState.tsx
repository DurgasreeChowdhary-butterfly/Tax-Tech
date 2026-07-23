import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col items-center gap-3 p-6 text-center text-gray-600 dark:text-gray-300">
      <p className="text-lg font-medium text-gray-900 dark:text-gray-100">{title}</p>
      {description && <p className="text-sm">{description}</p>}
      {action}
    </div>
  )
}
