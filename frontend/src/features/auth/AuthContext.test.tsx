import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthContext'
import { useAuth } from './useAuth'
import { tokenStorage } from '../../lib/tokenStorage'
import { authApi } from '../../api/auth'

vi.mock('../../api/auth', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}))

const mockedAuthApi = vi.mocked(authApi)

function Probe() {
  const { status, user, login, logout } = useAuth()
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="email">{user?.email ?? 'none'}</p>
      <button onClick={() => void login('user@example.com', 'password123')}>login</button>
      <button onClick={() => void logout()}>logout</button>
    </div>
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('goes straight to unauthenticated when no tokens are stored', async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated'))
    expect(mockedAuthApi.me).not.toHaveBeenCalled()
  })

  it('restores a session automatically when tokens are already stored', async () => {
    tokenStorage.setTokens('access-1', 'refresh-1')
    mockedAuthApi.me.mockResolvedValue({
      id: 'u1',
      email: 'restored@example.com',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'))
    expect(screen.getByTestId('email')).toHaveTextContent('restored@example.com')
  })

  it('drops back to unauthenticated and clears tokens if session restoration fails', async () => {
    tokenStorage.setTokens('access-1', 'refresh-1')
    mockedAuthApi.me.mockRejectedValue(new Error('unauthorized'))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated'))
    expect(tokenStorage.getAccessToken()).toBeNull()
  })

  it('login() stores tokens and fetches the user', async () => {
    mockedAuthApi.login.mockResolvedValue({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    mockedAuthApi.me.mockResolvedValue({
      id: 'u2',
      email: 'user@example.com',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated'))

    await user.click(screen.getByText('login'))

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'))
    expect(tokenStorage.getAccessToken()).toBe('a')
    expect(mockedAuthApi.login).toHaveBeenCalledWith({ email: 'user@example.com', password: 'password123' })
  })

  it('logout() clears tokens and local state even if the backend call fails', async () => {
    tokenStorage.setTokens('access-1', 'refresh-1')
    mockedAuthApi.me.mockResolvedValue({
      id: 'u1',
      email: 'user@example.com',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    mockedAuthApi.logout.mockRejectedValue(new Error('network error'))
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'))

    await act(async () => {
      await user.click(screen.getByText('logout'))
    })

    expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated')
    expect(tokenStorage.getAccessToken()).toBeNull()
  })
})
