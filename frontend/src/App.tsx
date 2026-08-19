import { useEffect, useState } from 'react'

import { AUTHENTICATION_REQUIRED_EVENT } from './api/client'
import { getSession, logout } from './authentication/api'
import { LoginScreen } from './authentication/LoginScreen'
import type { Session } from './authentication/types'
import { ConsultantDirectory } from './consultants/ConsultantDirectory'
import { PlanningPage } from './planning/PlanningPage'
import { SettingsPage } from './settings/SettingsPage'
import { AppIcon } from './system/AppIcon'
import { HealthStatus } from './system/HealthStatus'

type ApplicationWorkspaceProps = {
  onSignOut?: () => void
}

export function ApplicationWorkspace({ onSignOut }: ApplicationWorkspaceProps) {
  const [page, setPage] = useState<'consultants' | 'planning' | 'settings'>('consultants')

  return (
    <div className="application-frame">
      <div className="application-shell">
        <aside className="application-rail">
          <div className="brand" aria-hidden="true">
            <AppIcon name="calendar" />
          </div>

          <nav className="primary-navigation" aria-label="Primary navigation">
            <button
              className={`navigation-item${page === 'consultants' ? ' navigation-item--active' : ''}`}
              type="button"
              title="Consultants"
              aria-current={page === 'consultants' ? 'page' : undefined}
              onClick={() => setPage('consultants')}
            >
              <AppIcon name="consultants" />
              <span className="visually-hidden">Consultants</span>
            </button>
            <button
              className={`navigation-item${page === 'planning' ? ' navigation-item--active' : ''}`}
              type="button"
              title="Planning"
              aria-current={page === 'planning' ? 'page' : undefined}
              onClick={() => setPage('planning')}
            >
              <AppIcon name="wallchart" />
              <span className="visually-hidden">Planning</span>
            </button>
            <button
              className={`navigation-item${page === 'settings' ? ' navigation-item--active' : ''}`}
              type="button"
              title="Settings"
              aria-current={page === 'settings' ? 'page' : undefined}
              onClick={() => setPage('settings')}
            >
              <AppIcon name="settings" />
              <span className="visually-hidden">Settings</span>
            </button>
          </nav>

          <div className="rail-footer">
            {onSignOut ? (
              <button
                className="navigation-item"
                type="button"
                title="Sign Out"
                onClick={onSignOut}
              >
                <AppIcon name="logout" />
                <span className="visually-hidden">Sign Out</span>
              </button>
            ) : null}
            <HealthStatus />
          </div>
        </aside>

        <main className="application-content">
          {page === 'consultants' && <ConsultantDirectory />}
          {page === 'planning' && <PlanningPage />}
          {page === 'settings' && <SettingsPage />}
        </main>
      </div>
    </div>
  )
}

export function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    getSession()
      .then((nextSession) => {
        if (active) setSession(nextSession)
      })
      .catch(() => {
        if (active) {
          setUnavailable(true)
          setSession({ authenticated: false, user: null })
        }
      })

    const requireAuthentication = () => setSession({ authenticated: false, user: null })
    window.addEventListener(AUTHENTICATION_REQUIRED_EVENT, requireAuthentication)
    return () => {
      active = false
      window.removeEventListener(AUTHENTICATION_REQUIRED_EVENT, requireAuthentication)
    }
  }, [])

  if (session === null) {
    return (
      <div className="application-frame authentication-frame">
        <main className="authentication-page">
          <p className="authentication-loading" role="status">
            Connecting
          </p>
        </main>
      </div>
    )
  }

  if (!session.authenticated) {
    return (
      <LoginScreen
        unavailable={unavailable}
        onAuthenticated={(nextSession) => {
          setUnavailable(false)
          setSession(nextSession)
        }}
      />
    )
  }

  async function signOut() {
    try {
      await logout()
      setSession({ authenticated: false, user: null })
    } catch {
      // Keep the workspace visible when the server could not revoke the session.
    }
  }

  return <ApplicationWorkspace onSignOut={signOut} />
}
