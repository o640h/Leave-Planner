import { FormEvent, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
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

const modeCopy: Record<AccountActionMode, { title: string }> = {
  'forgot-password': {
    title: 'Reset Password',
  },
  'reset-password': {
    title: 'Choose New Password',
  },
  'verify-email': {
    title: 'Confirm Email',
  },
  'confirm-email': {
    title: 'Confirm New Email',
  },
  'change-email': {
    title: 'Change Email',
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
        <section
          className="authentication-panel authentication-panel--account authentication-panel--account-action"
          aria-labelledby="account-action-title"
        >
          <ProductIdentity />
          <div className="authentication-form-area">
            <header className="authentication-heading">
              <h1 id="account-action-title">{copy.title}</h1>
              <span className="authentication-account">
                <AppIcon name="profile" />
                Secure Account
              </span>
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
              <form className="authentication-account-form" noValidate onSubmit={submit}>
                {requestsEmail || changesEmail ? (
                  <div className="authentication-field">
                    <label htmlFor="action-email">
                      <AppIcon name="email" />
                      <span>{changesEmail ? 'New Email' : 'Email'}</span>
                    </label>
                    <div className="authentication-input-control">
                      <input
                        id="action-email"
                        type="email"
                        autoComplete="email"
                        placeholder=" "
                        autoFocus
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                      />
                    </div>
                  </div>
                ) : null}
                {changesEmail || resetsPassword ? (
                  <div className="authentication-field">
                    <label htmlFor="action-password">
                      <AppIcon name="lock" />
                      <span>{resetsPassword ? 'New Password' : 'Current Password'}</span>
                    </label>
                    <div className="authentication-input-control">
                      <input
                        id="action-password"
                        type="password"
                        autoComplete={resetsPassword ? 'new-password' : 'current-password'}
                        placeholder=" "
                        autoFocus={!requestsEmail && !changesEmail}
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                      />
                    </div>
                  </div>
                ) : null}
                {resetsPassword ? (
                  <div className="authentication-field">
                    <label htmlFor="action-password-confirmation">
                      <AppIcon name="lock" />
                      <span>Confirm New Password</span>
                    </label>
                    <div className="authentication-input-control">
                      <input
                        id="action-password-confirmation"
                        type="password"
                        autoComplete="new-password"
                        placeholder=" "
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                      />
                    </div>
                  </div>
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
          </div>
        </section>
      </main>
    </div>
  )
}
