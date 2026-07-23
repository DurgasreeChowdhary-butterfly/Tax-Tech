import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'
import { useAuth } from '../../features/auth/useAuth'
import type { AuthContextValue, AuthStatus } from '../../features/auth/AuthContext'

vi.mock('../../features/auth/useAuth')
const mockedUseAuth = vi.mocked(useAuth)

function authState(status: AuthStatus): AuthContextValue {
  return { status, user: null, login: vi.fn(), logout: vi.fn() }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<p>login page</p>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <p>secret content</p>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('shows a loading skeleton while the auth state is being restored', () => {
    mockedUseAuth.mockReturnValue(authState('restoring'))
    renderAt('/protected')
    expect(screen.getByTestId('page-skeleton')).toBeInTheDocument()
    expect(screen.queryByText('secret content')).not.toBeInTheDocument()
  })

  it('redirects to /login when unauthenticated', () => {
    mockedUseAuth.mockReturnValue(authState('unauthenticated'))
    renderAt('/protected')
    expect(screen.getByText('login page')).toBeInTheDocument()
    expect(screen.queryByText('secret content')).not.toBeInTheDocument()
  })

  it('renders the protected content when authenticated', () => {
    mockedUseAuth.mockReturnValue(authState('authenticated'))
    renderAt('/protected')
    expect(screen.getByText('secret content')).toBeInTheDocument()
  })
})
