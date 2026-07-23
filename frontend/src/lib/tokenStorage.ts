/**
 * Client-side persistence for the JWT access/refresh pair. localStorage
 * (not a cookie) matches docs/ARCHITECTURE.md's "Auth is token-based ...
 * rather than cookie/session tied to browser behavior, so it works
 * identically from a mobile app" — the same storage contract a future
 * React Native client can mirror with AsyncStorage/SecureStore behind the
 * same small interface.
 *
 * Never stores a password — only the two tokens the backend issues after a
 * successful login (see src/api/auth.ts).
 */

const ACCESS_TOKEN_KEY = 'itr_filing.access_token'
const REFRESH_TOKEN_KEY = 'itr_filing.refresh_token'

export const tokenStorage = {
  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY)
  },
  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  },
  setTokens(accessToken: string, refreshToken: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  },
  clear(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}
