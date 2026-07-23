import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../features/auth/useAuth'
import { PageSkeleton } from '../ui/Skeleton'

/** Route guard: renders children only once the auth context has confirmed
 * an authenticated user. Everything else — restoring, unauthenticated — is
 * handled here in one place, so no individual page re-implements the
 * "am I logged in" check. */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'restoring') {
    return <PageSkeleton />
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <>{children}</>
}
