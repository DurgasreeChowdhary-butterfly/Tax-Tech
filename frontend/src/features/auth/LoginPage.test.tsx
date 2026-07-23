import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'
import { useAuth } from './useAuth'
import { ApiError } from '../../api/client'
import type { AuthContextValue, AuthStatus } from './AuthContext'

vi.mock('./useAuth')
const mockedUseAuth = vi.mocked(useAuth)

function authState(status: AuthStatus, overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return { status, user: null, login: vi.fn(), logout: vi.fn(), ...overrides }
}

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<p>dashboard</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('shows validation errors instead of calling the API when fields are empty', async () => {
    const login = vi.fn()
    mockedUseAuth.mockReturnValue(authState('unauthenticated', { login }))
    const user = userEvent.setup()

    renderLogin()
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(screen.getByText('Enter your email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('calls login with the entered credentials', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    mockedUseAuth.mockReturnValue(authState('unauthenticated', { login }))
    const user = userEvent.setup()

    renderLogin()
    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(login).toHaveBeenCalledWith('user@example.com', 'password123'))
  })

  it('shows the backend error message verbatim on failed login', async () => {
    const login = vi.fn().mockRejectedValue(new ApiError(401, 'Incorrect email or password'))
    mockedUseAuth.mockReturnValue(authState('unauthenticated', { login }))
    const user = userEvent.setup()

    renderLogin()
    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Incorrect email or password')).toBeInTheDocument()
  })

  it('redirects away from /login when already authenticated', () => {
    mockedUseAuth.mockReturnValue(authState('authenticated'))
    renderLogin()
    expect(screen.getByText('dashboard')).toBeInTheDocument()
  })
})
