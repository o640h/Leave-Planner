import { FormEvent, useRef, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { HealthStatus } from '../system/HealthStatus'
import { ProductIdentity } from '../system/ProductIdentity'
import { login } from './api'
import type { Session } from './types'

type LoginScreenProps = {
  notice?: string | null
  onAuthenticated: (session: Session) => void
  onForgotPassword: () => void
}

export function LoginScreen({
  notice = null,
  onAuthenticated,
  onForgotPassword,
}: LoginScreenProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const submissionInProgress = useRef(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submissionInProgress.current) return
    setError(null)
    if (!email.trim()) {
      setError('Enter your email address.')
      return
    }
    if (!password) {
      setError('Enter your password.')
      return
    }

    submissionInProgress.current = true
    setSubmitting(true)
    try {
      const session = await login(email, password)
      setPassword('')
      onAuthenticated(session)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      submissionInProgress.current = false
      setSubmitting(false)
    }
  }

  const errorRelationship = error ? 'sign-in-error' : undefined

  return (
    <div className="application-frame authentication-frame">
      <main className="authentication-page">
        <section className="authentication-panel" aria-labelledby="sign-in-title">
          <ProductIdentity />

          <div className="authentication-form-area">
            <header className="authentication-heading">
              <div>
                <h1 id="sign-in-title">Sign In</h1>
                <p>Use the email address for your Leave Planner account.</p>
              </div>
              <span className="authentication-account">
                <AppIcon name="profile" />
                Secure Account
              </span>
            </header>

            {notice ? (
              <p className="authentication-notice" role="status">
                {notice}
              </p>
            ) : null}

            <form noValidate onSubmit={submit}>
              <label htmlFor="account-email">Email</label>
              <input
                id="account-email"
                name="email"
                type="email"
                autoComplete="email"
                autoFocus
                value={email}
                aria-invalid={error ? 'true' : undefined}
                aria-describedby={errorRelationship}
                onChange={(event) => setEmail(event.target.value)}
              />
              <label htmlFor="account-password">Password</label>
              <div className="authentication-password-control">
                <input
                  id="account-password"
                  name="password"
                  type={passwordVisible ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  aria-invalid={error ? 'true' : undefined}
                  aria-describedby={errorRelationship}
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
              <button className="button button--primary" type="submit" disabled={submitting}>
                {submitting ? 'Signing In' : 'Sign In'}
              </button>
            </form>

            <div className="authentication-secondary-actions">
              <button type="button" onClick={onForgotPassword}>
                Forgot Password
              </button>
            </div>

            <HealthStatus />
          </div>
        </section>
      </main>
    </div>
  )
}
