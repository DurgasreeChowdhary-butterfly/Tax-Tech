import { tokenStorage } from '../lib/tokenStorage'
import type { TokenPairResponse } from '../types/api'

/**
 * Centralized error type for every API call. `message` is always either the
 * backend's own safe `detail` string (Phase 10/11 guarantee the backend
 * never puts a stack trace or internal detail there) or a fixed generic
 * fallback — never raw response text, never a caught exception's message.
 */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Relative by default so the Vite dev proxy (vite.config.ts) makes every
 * request same-origin — no backend CORS configuration needed. A future
 * React Native client (no dev proxy available) would set this to an
 * absolute origin instead; nothing else in this file would need to change. */
const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

type UnauthorizedListener = () => void
let unauthorizedListener: UnauthorizedListener | null = null

/** Wired once by AuthProvider — called when a request's access token can't
 * be salvaged even after a refresh attempt, so the app can drop back to a
 * logged-out state. Kept as a single listener (not an event bus) since
 * there's exactly one consumer; add a real subscriber list only if a
 * second one is ever needed. */
export function setUnauthorizedListener(listener: UnauthorizedListener | null): void {
  unauthorizedListener = listener
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  /** A FormData body (e.g. a file upload) is sent as-is with no
   * Content-Type override, so the browser sets the correct multipart
   * boundary itself. Anything else is JSON-stringified. */
  body?: unknown | FormData
  /** Attach the stored access token. Defaults to true; auth endpoints that
   * take no token (login/register) or supply their own credential
   * (refresh/logout, which send the refresh token in the body) set this to
   * false. */
  auth?: boolean
}

async function sendOnce(path: string, options: RequestOptions): Promise<Response> {
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = {}
  if (!isFormData && options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.auth !== false) {
    const accessToken = tokenStorage.getAccessToken()
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  }
  return fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: isFormData ? (options.body as FormData) : options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })
}

// Concurrent 401s must not each fire their own refresh request — every
// caller that races into a refresh while one is already in flight awaits
// the SAME promise, and only the first caller actually hits the network.
let refreshInFlight: Promise<boolean> | null = null

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = tokenStorage.getRefreshToken()
  if (!refreshToken) return false

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await sendOnce('/auth/refresh', {
          method: 'POST',
          auth: false,
          body: { refresh_token: refreshToken },
        })
        if (!response.ok) return false
        const pair = (await response.json()) as TokenPairResponse
        tokenStorage.setTokens(pair.access_token, pair.refresh_token)
        return true
      } catch {
        return false
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

async function toApiError(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}.`
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body && typeof (body as { detail: unknown }).detail === 'string') {
      message = (body as { detail: string }).detail
    }
  } catch {
    // Non-JSON or empty body — keep the generic message. Never surface the
    // raw response text (it could be an HTML error page, a stack trace from
    // an unrelated proxy, etc.).
  }
  return new ApiError(response.status, message)
}

/**
 * The one function every API module (src/api/auth.ts, questionnaire.ts, ...)
 * calls through. JWT attachment, the refresh-and-retry-once flow, and error
 * normalization all live here so no feature/component ever talks to
 * `fetch` directly.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await sendOnce(path, options)

  if (response.status === 401 && options.auth !== false) {
    const refreshed = await refreshAccessToken()
    if (!refreshed) {
      tokenStorage.clear()
      unauthorizedListener?.()
      throw new ApiError(401, 'Your session has expired. Please log in again.')
    }
    response = await sendOnce(path, options) // retry exactly once
    if (response.status === 401) {
      // The refreshed token was rejected too — an unrecoverable auth
      // failure, not a retry loop.
      tokenStorage.clear()
      unauthorizedListener?.()
      throw new ApiError(401, 'Your session has expired. Please log in again.')
    }
  }

  if (!response.ok) {
    throw await toApiError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
