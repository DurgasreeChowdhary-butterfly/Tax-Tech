import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi } from '../../api/auth'
import { setUnauthorizedListener } from '../../api/client'
import { tokenStorage } from '../../lib/tokenStorage'
import type { UserRead } from '../../types/api'

export type AuthStatus = 'restoring' | 'authenticated' | 'unauthenticated'

export interface AuthContextValue {
  status: AuthStatus
  user: UserRead | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Owns the app's entire notion of "who is logged in". Session restoration
 * (on load, if tokens are already in storage) and forced logout (when the
 * API client gives up on a request after a failed refresh) both flow
 * through the same `user`/`status` state, so every consumer sees one
 * consistent picture regardless of which of those two paths produced it.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('restoring')
  const [user, setUser] = useState<UserRead | null>(null)

  const logout = useCallback(async () => {
    const refreshToken = tokenStorage.getRefreshToken()
    tokenStorage.clear()
    setUser(null)
    setStatus('unauthenticated')
    if (refreshToken) {
      // Best-effort: local state is already logged out regardless of
      // whether this network call succeeds (see docs — logout is designed
      // to be a safe no-op on the backend for an already-invalid token).
      try {
        await authApi.logout(refreshToken)
      } catch {
        // Tokens are already cleared client-side; nothing more to do.
      }
    }
  }, [])

  useEffect(() => {
    setUnauthorizedListener(() => {
      setUser(null)
      setStatus('unauthenticated')
    })
    return () => setUnauthorizedListener(null)
  }, [])

  // Automatic session restoration: if a token pair is already in storage
  // (from a previous visit), ask the backend who that is. apiRequest
  // transparently refreshes an expired access token before this ever
  // surfaces as a failure.
  useEffect(() => {
    let cancelled = false

    async function restore() {
      if (!tokenStorage.getAccessToken() && !tokenStorage.getRefreshToken()) {
        if (!cancelled) setStatus('unauthenticated')
        return
      }
      try {
        const restoredUser = await authApi.me()
        if (!cancelled) {
          setUser(restoredUser)
          setStatus('authenticated')
        }
      } catch {
        if (!cancelled) {
          tokenStorage.clear()
          setStatus('unauthenticated')
        }
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authApi.login({ email, password })
    tokenStorage.setTokens(tokens.access_token, tokens.refresh_token)
    const loggedInUser = await authApi.me()
    setUser(loggedInUser)
    setStatus('authenticated')
  }, [])

  const value = useMemo(() => ({ status, user, login, logout }), [status, user, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
