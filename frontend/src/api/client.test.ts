import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest, ApiError, setUnauthorizedListener } from './client'
import { tokenStorage } from '../lib/tokenStorage'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('apiRequest', () => {
  beforeEach(() => {
    localStorage.clear()
    setUnauthorizedListener(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('attaches the stored access token as a Bearer header', async () => {
    tokenStorage.setTokens('access-123', 'refresh-123')
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiRequest('/some/path')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer access-123')
  })

  it('does not attach a token when auth: false', async () => {
    tokenStorage.setTokens('access-123', 'refresh-123')
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiRequest('/auth/login', { method: 'POST', auth: false, body: {} })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('refreshes the access token once on a 401 and retries the original request', async () => {
    tokenStorage.setTokens('expired-access', 'valid-refresh')
    const fetchMock = vi
      .fn()
      // 1) original request -> 401
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Token has expired' }))
      // 2) refresh -> new pair
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'new-access', refresh_token: 'new-refresh', token_type: 'bearer' }))
      // 3) retried original request -> success
      .mockResolvedValueOnce(jsonResponse(200, { hello: 'world' }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiRequest<{ hello: string }>('/protected')

    expect(result).toEqual({ hello: 'world' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(tokenStorage.getAccessToken()).toBe('new-access')
    // The retried request must use the NEW token, not the expired one.
    const [, retryInit] = fetchMock.mock.calls[2] as [string, RequestInit]
    expect((retryInit.headers as Record<string, string>).Authorization).toBe('Bearer new-access')
  })

  it('never retries more than once, even if the refreshed token is also rejected', async () => {
    tokenStorage.setTokens('expired-access', 'valid-refresh')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Token has expired' }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'new-access', refresh_token: 'new-refresh', token_type: 'bearer' }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Could not validate credentials' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/protected')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(3) // original + refresh + one retry, never a second retry
  })

  it('clears tokens and calls the unauthorized listener when refresh fails outright', async () => {
    tokenStorage.setTokens('expired-access', 'invalid-refresh')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Token has expired' }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Invalid refresh token' }))
    vi.stubGlobal('fetch', fetchMock)

    const onUnauthorized = vi.fn()
    setUnauthorizedListener(onUnauthorized)

    await expect(apiRequest('/protected')).rejects.toBeInstanceOf(ApiError)
    expect(tokenStorage.getAccessToken()).toBeNull()
    expect(tokenStorage.getRefreshToken()).toBeNull()
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('deduplicates concurrent refresh attempts into a single network call', async () => {
    tokenStorage.setTokens('expired-access', 'valid-refresh')
    let refreshCalls = 0
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      const url = String(_url)
      if (url.includes('/auth/refresh')) {
        refreshCalls += 1
        return Promise.resolve(
          jsonResponse(200, { access_token: 'new-access', refresh_token: 'new-refresh', token_type: 'bearer' }),
        )
      }
      const hasFreshToken = (init?.headers as Record<string, string> | undefined)?.Authorization === 'Bearer new-access'
      return Promise.resolve(hasFreshToken ? jsonResponse(200, { ok: true }) : jsonResponse(401, { detail: 'Token has expired' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    await Promise.all([apiRequest('/a'), apiRequest('/b')])

    expect(refreshCalls).toBe(1)
  })

  it('surfaces the backend detail message, never raw response text', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('<html>Internal Server Error<pre>Traceback ...</pre></html>', { status: 500 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/boom', { auth: false })).rejects.toMatchObject({
      status: 500,
      message: expect.not.stringContaining('Traceback'),
    })
  })

  it('surfaces a typed ApiError with the backend detail on 4xx', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(400, { detail: 'expected a boolean value' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/bad', { auth: false })).rejects.toMatchObject({
      status: 400,
      message: 'expected a boolean value',
    })
  })
})
