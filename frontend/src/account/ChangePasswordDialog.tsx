import { FormEvent, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { changePassword } from '../authentication/api'
import { AppIcon } from '../system/AppIcon'
import { ModalLayer } from '../system/ModalLayer'

type ChangePasswordDialogProps = {
  onClose: () => void
}

export function ChangePasswordDialog({ onClose }: ChangePasswordDialogProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
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
    if (!currentPassword) {
      setError('Enter your current password.')
      return
    }
    if (password.length < 8) {
      setError('Use at least 8 characters for your new password.')
      return
    }
    if (password !== passwordConfirmation) {
      setError('The new passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      const result = await changePassword(currentPassword, password, passwordConfirmation)
      setCurrentPassword('')
      setPassword('')
      setPasswordConfirmation('')
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
          aria-labelledby="change-password-title"
          tabIndex={-1}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close Change Password"
            disabled={submitting}
            onClick={close}
          >
            x
          </button>

          <div className="form-introduction">
            <span className="section-label">Secure Account</span>
            <h2 id="change-password-title">Change Password</h2>
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
                  <label htmlFor="account-current-password-change">
                    <AppIcon name="lock" />
                    Current Password
                  </label>
                  <input
                    id="account-current-password-change"
                    type="password"
                    autoComplete="current-password"
                    autoFocus
                    value={currentPassword}
                    disabled={submitting}
                    onChange={(event) => {
                      setError(null)
                      setCurrentPassword(event.target.value)
                    }}
                  />
                </div>
                <div className="field">
                  <label htmlFor="account-new-password">
                    <AppIcon name="lock" />
                    New Password
                  </label>
                  <input
                    id="account-new-password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    disabled={submitting}
                    onChange={(event) => {
                      setError(null)
                      setPassword(event.target.value)
                    }}
                  />
                </div>
                <div className="field">
                  <label htmlFor="account-confirm-password">
                    <AppIcon name="lock" />
                    Confirm New Password
                  </label>
                  <input
                    id="account-confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={passwordConfirmation}
                    disabled={submitting}
                    onChange={(event) => {
                      setError(null)
                      setPasswordConfirmation(event.target.value)
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
                  {submitting ? 'Changing...' : 'Change Password'}
                </button>
              </div>
            </form>
          )}
        </section>
      </div>
    </ModalLayer>
  )
}
