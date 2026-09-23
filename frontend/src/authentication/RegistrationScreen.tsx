import { FormEvent, useRef, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { ProductIdentity } from '../system/ProductIdentity'
import { registerAccount } from './api'

type RegistrationScreenProps = {
  onBack: (notice?: string) => void
  invitationToken?: string
}

export function RegistrationScreen({ onBack, invitationToken }: RegistrationScreenProps) {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const submissionInProgress = useRef(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submissionInProgress.current) return
    setError(null)

    if (!displayName.trim()) {
      setError('Enter your name.')
      return
    }
    if (!email.trim()) {
      setError('Enter your email address.')
      return
    }
    if (password.length < 8) {
      setError('Use at least 8 characters for your password.')
      return
    }
    if (password !== confirmation) {
      setError('The passwords do not match.')
      return
    }

    submissionInProgress.current = true
    setSubmitting(true)
    try {
      const result = await registerAccount(
        displayName.trim(),
        email.trim(),
        password,
        invitationToken,
      )
      setPassword('')
      setConfirmation('')
      onBack(result.message)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      submissionInProgress.current = false
      setSubmitting(false)
    }
  }

  const errorRelationship = error ? 'registration-error' : undefined

  return (
    <div className="application-frame authentication-frame">
      <main className="authentication-page">
        <section
          className="authentication-panel authentication-panel--account authentication-panel--registration"
          aria-labelledby="registration-title"
        >
          <ProductIdentity />
          <div className="authentication-form-area">
            <header className="authentication-heading">
              <h1 id="registration-title">Create Account</h1>
              <span className="authentication-account">
                <AppIcon name="profile" />
                Secure Account
              </span>
            </header>

            <form className="authentication-account-form" noValidate onSubmit={submit}>
              <div className="authentication-field">
                <label htmlFor="registration-name">
                  <AppIcon name="profile" />
                  <span>Name</span>
                </label>
                <div className="authentication-input-control">
                  <input
                    id="registration-name"
                    name="name"
                    autoComplete="name"
                    placeholder=" "
                    autoFocus
                    maxLength={100}
                    value={displayName}
                    aria-invalid={error ? 'true' : undefined}
                    aria-describedby={errorRelationship}
                    onChange={(event) => setDisplayName(event.target.value)}
                  />
                </div>
              </div>
              <div className="authentication-field">
                <label htmlFor="registration-email">
                  <AppIcon name="email" />
                  <span>Email</span>
                </label>
                <div className="authentication-input-control">
                  <input
                    id="registration-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    placeholder=" "
                    value={email}
                    aria-invalid={error ? 'true' : undefined}
                    aria-describedby={errorRelationship}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </div>
              </div>
              <div className="authentication-field">
                <label htmlFor="registration-password">
                  <AppIcon name="lock" />
                  <span>Password</span>
                </label>
                <div className="authentication-input-control">
                  <input
                    id="registration-password"
                    name="password"
                    type="password"
                    autoComplete="new-password"
                    placeholder=" "
                    value={password}
                    aria-invalid={error ? 'true' : undefined}
                    aria-describedby={errorRelationship}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </div>
              </div>
              <div className="authentication-field">
                <label htmlFor="registration-confirmation">
                  <AppIcon name="lock" />
                  <span>Confirm Password</span>
                </label>
                <div className="authentication-input-control">
                  <input
                    id="registration-confirmation"
                    name="password_confirmation"
                    type="password"
                    autoComplete="new-password"
                    placeholder=" "
                    value={confirmation}
                    aria-invalid={error ? 'true' : undefined}
                    aria-describedby={errorRelationship}
                    onChange={(event) => setConfirmation(event.target.value)}
                  />
                </div>
              </div>
              {error ? (
                <p className="authentication-error" id="registration-error" role="alert">
                  {error}
                </p>
              ) : null}
              <button className="button button--primary" type="submit" disabled={submitting}>
                {submitting ? 'Creating Account' : 'Create Account'}
              </button>
              <p className="authentication-legal-note">
                Read the <a href="/terms">Terms</a> and <a href="/privacy">Privacy</a> information
                before creating an account.
              </p>
            </form>

            <div className="authentication-secondary-actions">
              <button type="button" onClick={() => onBack()}>
                Back To Sign In
              </button>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
