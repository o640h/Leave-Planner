import { FormEvent, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { requestEmailChange } from '../authentication/api'
import type { AuthenticatedUser } from '../authentication/types'
import { AppIcon } from '../system/AppIcon'
import { ModalLayer } from '../system/ModalLayer'

type ChangeEmailDialogProps = {
  user: AuthenticatedUser
  onClose: () => void
}

export function ChangeEmailDialog({ user, onClose }: ChangeEmailDialogProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function close() {
    if (!submitting) onClose()
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    if (!email.trim()) {
      setError('Enter your new email address.')
      return
    }
    if (!password) {
      setError('Enter your current password.')
      return
    }

    setSubmitting(true)
    try {
      const result = await requestEmailChange(email, password)
      setPassword('')
      setMessage(result.message)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <ModalLayer onClose={close}>
      <div className="modal-backdrop">
        <section
          className="record-modal record-modal--lined account-action-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="change-email-title"
          tabIndex={-1}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close Change Email"
            disabled={submitting}
            onClick={close}
          >
            x
          </button>

          <div className="form-introduction">
            <span className="section-label">Secure Account</span>
            <h2 id="change-email-title">Change Email</h2>
            <p>Current email: {user.display_email}</p>
          </div>

          {message ? (
            <>
              <p className="account-action-message" role="status">
                {message}
              </p>
              <div className="form-actions">
                <button className="button button--primary" type="button" onClick={close}>
                  Close
                </button>
              </div>
            </>
          ) : (
            <form noValidate onSubmit={submit}>
              <div className="form-fields">
                <div className="field">
                  <label htmlFor="account-new-email">
                    <AppIcon name="email" />
                    New Email
                  </label>
                  <input
                    id="account-new-email"
                    type="email"
                    autoComplete="email"
                    autoFocus
                    value={email}
                    aria-invalid={error && !email.trim() ? 'true' : undefined}
                    disabled={submitting}
                    onChange={(event) => {
                      setError(null)
                      setEmail(event.target.value)
                    }}
                  />
                </div>
                <div className="field">
                  <label htmlFor="account-current-password">
                    <AppIcon name="lock" />
                    Current Password
                  </label>
                  <input
                    id="account-current-password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    aria-invalid={error && !password ? 'true' : undefined}
                    disabled={submitting}
                    onChange={(event) => {
                      setError(null)
                      setPassword(event.target.value)
                    }}
                  />
                </div>
              </div>
              {error ? (
                <p className="form-error" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="form-actions">
                <button
                  className="button button--quiet"
                  type="button"
                  disabled={submitting}
                  onClick={close}
                >
                  Cancel
                </button>
                <button className="button button--primary" type="submit" disabled={submitting}>
                  {submitting ? 'Sending...' : 'Send Confirmation'}
                </button>
              </div>
            </form>
          )}
        </section>
      </div>
    </ModalLayer>
  )
}
