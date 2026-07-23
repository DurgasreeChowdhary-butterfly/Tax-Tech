import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { TextField } from '../../components/ui/TextField'
import { ApiError } from '../../api/client'
import { useAuth } from './useAuth'

interface LocationState {
  from?: { pathname: string }
}

export function LoginPage() {
  const { status, login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({})

  if (status === 'authenticated') {
    const redirectTo = (location.state as LocationState | null)?.from?.pathname ?? '/'
    return <Navigate to={redirectTo} replace />
  }

  function validate(): boolean {
    const next: { email?: string; password?: string } = {}
    if (!email.trim()) next.email = 'Enter your email address.'
    if (!password) next.password = 'Enter your password.'
    setFieldErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    if (!validate()) return

    setSubmitting(true)
    try {
      await login(email.trim(), password)
    } catch (error) {
      // The backend deliberately returns the same generic message whether
      // the email or the password was wrong (Phase 11) — surfaced as-is,
      // never replaced with a more "helpful" (and enumeration-leaking) one.
      setFormError(error instanceof ApiError ? error.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <h1 className="mb-6 text-center text-2xl font-semibold text-gray-900 dark:text-gray-100">Log in</h1>
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldErrors.email}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
          />
          {formError && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {formError}
            </p>
          )}
          <Button type="submit" loading={submitting}>
            Log in
          </Button>
        </form>
      </div>
    </div>
  )
}
