import { FormEvent, useEffect, useRef, useState } from 'react'

import { ApiClientError, operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { HealthStatus } from '../system/HealthStatus'
import { ProductIdentity } from '../system/ProductIdentity'
import { login } from './api'
import type { Session } from './types'

type LoginScreenProps = {
  notice?: string | null
  onAuthenticated: (session: Session) => void
}

function lockoutSeconds(error: unknown): number | null {
  if (
    !(error instanceof ApiClientError) ||
    error.code !== 'login_unavailable' ||
    typeof error.details !== 'object' ||
    error.details === null
  ) {
    return null
  }

  const retryAfter = (error.details as { retry_after_seconds?: unknown }).retry_after_seconds
  return typeof retryAfter === 'number' && retryAfter > 0 ? Math.ceil(retryAfter) : null
}

function countdown(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

export function LoginScreen({ notice = null, onAuthenticated }: LoginScreenProps) {
  const [password, setPassword] = useState('')
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [lockedUntil, setLockedUntil] = useState<number | null>(null)
  const [remainingSeconds, setRemainingSeconds] = useState(0)
  const submissionInProgress = useRef(false)

  useEffect(() => {
    if (lockedUntil === null) return

    const updateRemaining = () => {
      const remaining = Math.max(0, Math.ceil((lockedUntil - Date.now()) / 1000))
      setRemainingSeconds(remaining)
      if (remaining === 0) setLockedUntil(null)
    }

    updateRemaining()
    const timer = window.setInterval(updateRemaining, 1000)
    return () => window.clearInterval(timer)
  }, [lockedUntil])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submissionInProgress.current || remainingSeconds > 0) return
    setError(null)
    if (!password) {
      setError('Enter the Admin password.')
      return
    }

    submissionInProgress.current = true
    setSubmitting(true)
    try {
      const session = await login(password)
      setPassword('')
      onAuthenticated(session)
    } catch (requestError) {
      const retryAfter = lockoutSeconds(requestError)
      if (retryAfter === null) {
        setError(operatorErrorMessage(requestError))
      } else {
        setLockedUntil(Date.now() + retryAfter * 1000)
        setRemainingSeconds(retryAfter)
      }
    } finally {
      submissionInProgress.current = false
      setSubmitting(false)
    }
  }

  return (
    <div className="application-frame authentication-frame">
      <main className="authentication-page">
        <section className="authentication-panel" aria-labelledby="sign-in-title">
          <ProductIdentity />

          <div className="authentication-form-area">
            <header className="authentication-heading">
              <div>
                <h1 id="sign-in-title">Sign In</h1>
                <p>Enter the password for the protected workspace.</p>
              </div>
              <span className="authentication-account">
                <AppIcon name="profile" />
                Admin
              </span>
            </header>

            {notice ? (
              <p className="authentication-notice" role="status">
                {notice}
              </p>
            ) : null}

            <form noValidate onSubmit={submit}>
              <label htmlFor="admin-password">Password</label>
              <div className="authentication-password-control">
                <input
                  id="admin-password"
                  name="password"
                  type={passwordVisible ? 'text' : 'password'}
                  autoComplete="current-password"
                  autoFocus
                  value={password}
                  aria-invalid={error ? 'true' : undefined}
                  aria-describedby={error ? 'sign-in-error' : undefined}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  className="authentication-password-toggle"
                  type="button"
                  aria-pressed={passwordVisible}
                  onClick={() => setPasswordVisible((visible) => !visible)}
                >
                  {passwordVisible ? 'Hide' : 'Show'}
                </button>
              </div>
              {error ? (
                <p className="authentication-error" id="sign-in-error" role="alert">
                  {error}
                </p>
              ) : null}
              {remainingSeconds > 0 ? (
                <p className="authentication-lockout" role="alert">
                  Admin is temporarily locked. Try again when the countdown ends.
                  <strong aria-hidden="true">{countdown(remainingSeconds)}</strong>
                </p>
              ) : null}
              <button
                className="button button--primary"
                type="submit"
                disabled={submitting || remainingSeconds > 0}
              >
                {submitting ? 'Signing In' : 'Sign In'}
              </button>
            </form>

            <HealthStatus />
          </div>
        </section>
      </main>
    </div>
  )
}
