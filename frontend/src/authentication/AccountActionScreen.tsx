import { FormEvent, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { HealthStatus } from '../system/HealthStatus'
import { ProductIdentity } from '../system/ProductIdentity'
import {
  confirmEmailChange,
  confirmEmailVerification,
  confirmPasswordReset,
  requestEmailChange,
  requestPasswordReset,
} from './api'

export type AccountActionMode =
  'forgot-password' | 'reset-password' | 'verify-email' | 'confirm-email' | 'change-email'

type AccountActionScreenProps = {
  mode: AccountActionMode
  token?: string
  currentEmail?: string
  onBack: (notice?: string) => void
}

const modeCopy: Record<AccountActionMode, { title: string; description: string }> = {
  'forgot-password': {
    title: 'Reset Password',
    description: 'Enter your account email and we will send the next step.',
  },
  'reset-password': {
    title: 'Choose New Password',
    description: 'Use the secure link from your password-reset email.',
  },
  'verify-email': {
    title: 'Confirm Email',
    description: 'Complete verification for your Leave Planner account.',
  },
  'confirm-email': {
    title: 'Confirm New Email',
    description: 'Complete the requested change to your sign-in email.',
  },
  'change-email': {
    title: 'Change Email',
    description: 'Confirm your password and enter the new sign-in address.',
  },
}

export function AccountActionScreen({
  mode,
  token = '',
  currentEmail,
  onBack,
}: AccountActionScreenProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const copy = modeCopy[mode]
  const requestsEmail = mode === 'forgot-password'
  const changesEmail = mode === 'change-email'
  const resetsPassword = mode === 'reset-password'
  const confirmsToken = mode === 'verify-email' || mode === 'confirm-email'

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    if ((requestsEmail || changesEmail) && !email.trim()) {
      setError('Enter your email address.')
      return
    }
    if ((changesEmail || resetsPassword) && !password) {
      setError('Enter your password.')
      return
    }
    if (resetsPassword && password.length < 8) {
      setError('Password must contain at least 8 characters.')
      return
    }
    if (resetsPassword && password !== confirmation) {
      setError('The passwords do not match.')
      return
    }
    if ((resetsPassword || confirmsToken) && !token) {
      setError('This link is missing its secure token.')
      return
    }

    setSubmitting(true)
    try {
      const result =
        mode === 'forgot-password'
          ? await requestPasswordReset(email)
          : mode === 'reset-password'
            ? await confirmPasswordReset(token, password)
            : mode === 'verify-email'
              ? await confirmEmailVerification(token)
              : mode === 'confirm-email'
                ? await confirmEmailChange(token)
                : await requestEmailChange(email, password)
      setPassword('')
      setConfirmation('')
      setMessage(result.message)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  const completedAccountChange = message && (resetsPassword || confirmsToken)
  return (
    <div className="application-frame authentication-frame">
      <main className="authentication-page">
        <section className="authentication-panel" aria-labelledby="account-action-title">
          <ProductIdentity />
          <div className="authentication-form-area">
            <header className="authentication-heading">
              <div>
                <h1 id="account-action-title">{copy.title}</h1>
                <p>{copy.description}</p>
              </div>
            </header>

            {currentEmail ? (
              <p className="authentication-notice">Current email: {currentEmail}</p>
            ) : null}
            {message ? (
              <p className="authentication-notice" role="status">
                {message}
              </p>
            ) : null}

            {!completedAccountChange ? (
              <form noValidate onSubmit={submit}>
                {requestsEmail || changesEmail ? (
                  <>
                    <label htmlFor="action-email">{changesEmail ? 'New Email' : 'Email'}</label>
                    <input
                      id="action-email"
                      type="email"
                      autoComplete="email"
                      autoFocus
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </>
                ) : null}
                {changesEmail || resetsPassword ? (
                  <>
                    <label htmlFor="action-password">
                      {resetsPassword ? 'New Password' : 'Current Password'}
                    </label>
                    <input
                      id="action-password"
                      type="password"
                      autoComplete={resetsPassword ? 'new-password' : 'current-password'}
                      autoFocus={!requestsEmail && !changesEmail}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  </>
                ) : null}
                {resetsPassword ? (
                  <>
                    <label htmlFor="action-password-confirmation">Confirm New Password</label>
                    <input
                      id="action-password-confirmation"
                      type="password"
                      autoComplete="new-password"
                      value={confirmation}
                      onChange={(event) => setConfirmation(event.target.value)}
                    />
                  </>
                ) : null}
                {error ? (
                  <p className="authentication-error" role="alert">
                    {error}
                  </p>
                ) : null}
                <button className="button button--primary" type="submit" disabled={submitting}>
                  {submitting
                    ? 'Working'
                    : confirmsToken
                      ? 'Confirm Email'
                      : changesEmail
                        ? 'Send Confirmation'
                        : resetsPassword
                          ? 'Change Password'
                          : 'Send Link'}
                </button>
              </form>
            ) : null}

            <div className="authentication-secondary-actions">
              <button type="button" onClick={() => onBack(message ?? undefined)}>
                {currentEmail && !completedAccountChange ? 'Back To Account' : 'Back To Sign In'}
              </button>
            </div>
            <HealthStatus />
          </div>
        </section>
      </main>
    </div>
  )
}
