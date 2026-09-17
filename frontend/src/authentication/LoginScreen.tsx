import { FormEvent, useRef, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { ProductIdentity } from '../system/ProductIdentity'
import { login } from './api'
import type { Session } from './types'

type LoginScreenProps = {
  notice?: string | null
  onAuthenticated: (session: Session) => void
  onForgotPassword: () => void
  onRegister?: () => void
}

export function LoginScreen({
  notice = null,
  onAuthenticated,
  onForgotPassword,
  onRegister,
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
        <section
          className="authentication-panel authentication-panel--account authentication-panel--sign-in"
          aria-labelledby="sign-in-title"
        >
          <ProductIdentity />

          <div className="authentication-form-area">
            <header className="authentication-heading">
              <h1 id="sign-in-title">Sign In</h1>
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

            <form className="authentication-sign-in-form" noValidate onSubmit={submit}>
              <div className="authentication-field">
                <label htmlFor="account-email">
                  <AppIcon name="email" />
                  <span>Email</span>
                </label>
                <div className="authentication-input-control">
                  <input
                    id="account-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    placeholder=" "
                    autoFocus
                    value={email}
                    aria-invalid={error ? 'true' : undefined}
                    aria-describedby={errorRelationship}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </div>
              </div>
              <div className="authentication-field">
                <label htmlFor="account-password">
                  <AppIcon name="lock" />
                  <span>Password</span>
                </label>
                <div className="authentication-input-control authentication-password-control">
                  <input
                    id="account-password"
                    name="password"
                    type={passwordVisible ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder=" "
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
              {onRegister ? (
                <button type="button" onClick={onRegister}>
                  Create Account
                </button>
              ) : null}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
