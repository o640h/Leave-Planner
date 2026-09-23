import { useEffect, useState } from 'react'

import type { AuthenticatedUser } from '../authentication/types'
import { PublicLinks } from '../publicSite/PublicSite'
import { AppIcon } from '../system/AppIcon'
import { ModalLayer } from '../system/ModalLayer'
import { ChangeEmailDialog } from './ChangeEmailDialog'
import { ChangePasswordDialog } from './ChangePasswordDialog'
import './account.css'

type AccountPageProps = {
  user: AuthenticatedUser
}

type AccountDialogProps = AccountPageProps & {
  closeRequested?: boolean
  onClose: () => void
}

export function AccountDialog({ user, closeRequested = false, onClose }: AccountDialogProps) {
  const [closing, setClosing] = useState(false)
  const isClosing = closing || closeRequested

  useEffect(() => {
    if (!isClosing) return
    const timeout = window.setTimeout(onClose, 220)
    return () => window.clearTimeout(timeout)
  }, [isClosing, onClose])

  function requestClose() {
    setClosing(true)
  }

  return (
    <ModalLayer onClose={requestClose}>
      <div
        className={`modal-backdrop account-popout-backdrop${
          isClosing ? ' account-popout-backdrop--closing' : ''
        }`}
      >
        <section
          className={`account-popout${isClosing ? ' account-popout--closing' : ''}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby="account-page-title"
          tabIndex={-1}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close Account"
            disabled={isClosing}
            onClick={requestClose}
          >
            x
          </button>
          <AccountPage user={user} />
        </section>
      </div>
    </ModalLayer>
  )
}

export function AccountPage({ user }: AccountPageProps) {
  const [changingEmail, setChangingEmail] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)

  return (
    <>
      <section className="account-page" aria-labelledby="account-page-title">
        <header className="account-page-heading">
          <span className="section-label">Personal Account</span>
          <h1 id="account-page-title">Account</h1>
        </header>

        <section className="account-section" aria-labelledby="account-identity-title">
          <header>
            <AppIcon name="profile" />
            <div>
              <span className="section-label">Signed-In Identity</span>
              <h2 id="account-identity-title">Profile</h2>
            </div>
          </header>
          <dl className="account-details">
            <div>
              <dt>Display Name</dt>
              <dd>{user.display_name}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{user.display_email}</dd>
            </div>
          </dl>
        </section>

        <section className="account-section" aria-labelledby="account-security-title">
          <header>
            <AppIcon name="lock" />
            <div>
              <span className="section-label">Account Access</span>
              <h2 id="account-security-title">Security</h2>
            </div>
          </header>
          <div className="account-action-row">
            <div>
              <strong>Email Address</strong>
              <span>Change the address used to sign in.</span>
            </div>
            <button
              className="button button--overview-action"
              type="button"
              onClick={() => setChangingEmail(true)}
            >
              Change Email
            </button>
          </div>
          <div className="account-action-row">
            <div>
              <strong>Password</strong>
              <span>Choose a new password using a secure email link.</span>
            </div>
            <button
              className="button button--overview-action"
              type="button"
              onClick={() => setChangingPassword(true)}
            >
              Change Password
            </button>
          </div>
        </section>
        <section className="account-section" aria-labelledby="account-information-title">
          <header>
            <AppIcon name="document" />
            <div>
              <span className="section-label">Merydio</span>
              <h2 id="account-information-title">Information &amp; Contact</h2>
            </div>
          </header>
          <div className="account-information-links">
            <PublicLinks />
          </div>
        </section>
      </section>

      {changingEmail ? (
        <ChangeEmailDialog user={user} onClose={() => setChangingEmail(false)} />
      ) : null}
      {changingPassword ? (
        <ChangePasswordDialog onClose={() => setChangingPassword(false)} />
      ) : null}
    </>
  )
}
