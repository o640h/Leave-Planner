import { FormEvent, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { HealthStatus } from '../system/HealthStatus'
import { login } from './api'
import type { Session } from './types'

type LoginScreenProps = {
  unavailable?: boolean
  onAuthenticated: (session: Session) => void
}

export function LoginScreen({ unavailable = false, onAuthenticated }: LoginScreenProps) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (!password) {
      setError('Enter the Admin password.')
      return
    }

    setSubmitting(true)
    try {
      const session = await login(password)
      setPassword('')
      onAuthenticated(session)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="application-frame authentication-frame">
      <main className="authentication-page">
        <section className="authentication-panel" aria-labelledby="sign-in-title">
          <div className="authentication-mark" aria-hidden="true">
            <AppIcon name="calendar" />
          </div>
          <p className="authentication-product">Leave Planner</p>
          <h1 id="sign-in-title">Sign In</h1>
          <p className="authentication-account">Admin</p>

          {unavailable ? (
            <p className="authentication-notice" role="status">
              The service is unavailable. Check the server and try again.
            </p>
          ) : null}

          <form noValidate onSubmit={submit}>
            <label htmlFor="admin-password">Password</label>
            <input
              id="admin-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              aria-invalid={error ? 'true' : undefined}
              aria-describedby={error ? 'sign-in-error' : undefined}
              onChange={(event) => setPassword(event.target.value)}
            />
            {error ? (
              <p className="authentication-error" id="sign-in-error" role="alert">
                {error}
              </p>
            ) : null}
            <button className="button button--primary" type="submit" disabled={submitting}>
              {submitting ? 'Signing In' : 'Sign In'}
            </button>
          </form>

          <HealthStatus />
        </section>
      </main>
    </div>
  )
}
