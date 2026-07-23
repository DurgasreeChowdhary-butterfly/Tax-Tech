export function Skeleton({ className = '' }: { className?: string }) {
  return <div role="status" aria-label="Loading" className={`animate-pulse rounded-md bg-gray-200 dark:bg-gray-700 ${className}`} />
}

export function PageSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4 p-4" data-testid="page-skeleton">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-12 w-full" />
    </div>
  )
}
