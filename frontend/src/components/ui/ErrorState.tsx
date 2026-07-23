import { Button } from './Button'

interface ErrorStateProps {
  message: string
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="mx-auto flex w-full max-w-md flex-col items-center gap-4 p-6 text-center">
      <p className="text-base text-red-600 dark:text-red-400">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} className="max-w-xs">
          Try again
        </Button>
      )}
    </div>
  )
}
