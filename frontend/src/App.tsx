import { useEffect, useState } from 'react'

import {
  AUTHENTICATION_REQUIRED_EVENT,
  AUTHORIZATION_DENIED_EVENT,
  SERVICE_UNAVAILABLE_EVENT,
} from './api/client'
import { getSession, logout } from './authentication/api'
import { LoginScreen } from './authentication/LoginScreen'
import type { AuthenticatedUser, Session, WorkspaceContext } from './authentication/types'
import { ConsultantDirectory } from './consultants/ConsultantDirectory'
import { PlanningPage } from './planning/PlanningPage'
import { SettingsPage } from './settings/SettingsPage'
import { AppIcon } from './system/AppIcon'
import { HealthStatus } from './system/HealthStatus'
import { ProductIdentity } from './system/ProductIdentity'
import { WorkspaceFrame } from './system/WorkspaceFrame'
import { WorkspaceSelector } from './workspaces/WorkspaceSelector'

type ApplicationWorkspaceProps = {
  user?: AuthenticatedUser
  onSignOut?: () => void
  signOutError?: string | null
  workspace?: WorkspaceContext
  onWorkspaceSelected?: (context: WorkspaceContext) => void
}

export function ApplicationWorkspace({
  user,
  onSignOut,
  signOutError,
  workspace,
  onWorkspaceSelected,
}: ApplicationWorkspaceProps) {
  const [page, setPage] = useState<'consultants' | 'planning' | 'settings'>('consultants')

  return (
    <WorkspaceFrame>
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
            {user ? (
              <div className="account-indicator" title={`Signed In As ${user.display_name}`}>
                <AppIcon name="profile" />
                <span className="visually-hidden">Signed In As {user.display_name}</span>
              </div>
            ) : null}
            {onSignOut ? (
              <button
                className="navigation-item"
                type="button"
                title={user ? `Sign Out ${user.display_name}` : 'Sign Out'}
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
          {workspace && workspace.memberships.length > 1 && onWorkspaceSelected ? (
            <WorkspaceSelector context={workspace} onSelected={onWorkspaceSelected} />
          ) : null}
          {signOutError ? (
            <p className="application-notice" role="alert">
              {signOutError}
            </p>
          ) : null}
          {page === 'consultants' && <ConsultantDirectory />}
          {page === 'planning' && <PlanningPage />}
          {page === 'settings' && <SettingsPage />}
        </main>
      </div>
    </WorkspaceFrame>
  )
}

type ApplicationStatusProps = {
  kind: 'access-denied' | 'member' | 'onboarding' | 'unavailable'
  busy?: boolean
  onRetry?: () => void
  onSignOut?: () => void
}

function ApplicationStatus({ kind, busy = false, onRetry, onSignOut }: ApplicationStatusProps) {
  const unavailable = kind === 'unavailable'
  const title = unavailable
    ? 'Server Unavailable'
    : kind === 'onboarding'
      ? 'Workspace Setup Required'
      : kind === 'member'
        ? 'Member Workspace'
        : 'Workspace Access Unavailable'
  const message = unavailable
    ? 'Leave Planner could not reach the server. Check the connection and try again.'
    : kind === 'onboarding'
      ? 'Your account is ready. A workspace can be created during the Owner setup step.'
      : kind === 'member'
        ? 'Your membership is active. The read-only consultant workspace will be enabled separately.'
        : 'Your account is signed in but does not currently have access to the selected workspace.'
  return (
    <div className="application-frame authentication-frame">
      <main className="application-status-page">
        <section
          className="authentication-panel application-status-panel"
          aria-labelledby="application-status-title"
        >
          <ProductIdentity />
          <div className="application-status-content">
            <div className="application-status-mark" aria-hidden="true">
              <AppIcon name={unavailable ? 'server' : 'profile'} />
            </div>
            <h1 id="application-status-title">{title}</h1>
            <p>{message}</p>
            <div className="application-status-actions">
              {onRetry ? (
                <button
                  className="button button--primary button--with-icon"
                  type="button"
                  disabled={busy}
                  onClick={onRetry}
                >
                  <AppIcon name="retry" />
                  {busy ? 'Checking' : 'Try Again'}
                </button>
              ) : null}
              {onSignOut ? (
                <button className="button button--quiet" type="button" onClick={onSignOut}>
                  Sign Out
                </button>
              ) : null}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [applicationState, setApplicationState] = useState<
    'ready' | 'access-denied' | 'unavailable'
  >('ready')
  const [loginNotice, setLoginNotice] = useState<string | null>(null)
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    let active = true
    getSession()
      .then((nextSession) => {
        if (active) {
          setSession(nextSession)
          setApplicationState('ready')
        }
      })
      .catch(() => {
        if (active) {
          setApplicationState('unavailable')
        }
      })

    const requireAuthentication = () => {
      setApplicationState('ready')
      setLoginNotice('Your session expired. Sign in again to continue.')
      setSession({ authenticated: false, user: null, workspace: null })
    }
    const denyAuthorization = () => setApplicationState('access-denied')
    const reportUnavailable = () => setApplicationState('unavailable')
    window.addEventListener(AUTHENTICATION_REQUIRED_EVENT, requireAuthentication)
    window.addEventListener(AUTHORIZATION_DENIED_EVENT, denyAuthorization)
    window.addEventListener(SERVICE_UNAVAILABLE_EVENT, reportUnavailable)
    return () => {
      active = false
      window.removeEventListener(AUTHENTICATION_REQUIRED_EVENT, requireAuthentication)
      window.removeEventListener(AUTHORIZATION_DENIED_EVENT, denyAuthorization)
      window.removeEventListener(SERVICE_UNAVAILABLE_EVENT, reportUnavailable)
    }
  }, [])

  async function retryConnection() {
    setRetrying(true)
    try {
      const nextSession = await getSession()
      setSession(nextSession)
      setApplicationState('ready')
    } catch {
      setApplicationState('unavailable')
    } finally {
      setRetrying(false)
    }
  }

  async function signOut() {
    setSignOutError(null)
    try {
      await logout()
      setApplicationState('ready')
      setLoginNotice('You have signed out.')
      setSession({ authenticated: false, user: null, workspace: null })
    } catch {
      setSignOutError('Sign out could not be completed. Check the server and try again.')
    }
  }

  if (applicationState === 'unavailable') {
    return <ApplicationStatus kind="unavailable" busy={retrying} onRetry={retryConnection} />
  }

  if (applicationState === 'access-denied') {
    return <ApplicationStatus kind="access-denied" onSignOut={signOut} />
  }

  if (session === null) {
    return (
      <div className="application-frame authentication-frame">
        <main className="application-status-page">
          <section
            className="authentication-panel application-status-panel application-status-panel--loading"
            aria-labelledby="application-loading-title"
          >
            <ProductIdentity />
            <div className="application-status-content" role="status">
              <div className="application-status-mark" aria-hidden="true">
                <AppIcon name="server" />
              </div>
              <h1 id="application-loading-title">Connecting</h1>
            </div>
          </section>
        </main>
      </div>
    )
  }

  if (!session.authenticated) {
    return (
      <LoginScreen
        notice={loginNotice}
        onAuthenticated={(nextSession) => {
          setApplicationState('ready')
          setLoginNotice(null)
          setSession(nextSession)
        }}
      />
    )
  }

  const workspace = session.workspace
  if (!workspace || workspace.state === 'onboarding') {
    return <ApplicationStatus kind="onboarding" onSignOut={signOut} />
  }

  if (workspace.state === 'selection_required') {
    return (
      <div className="application-frame authentication-frame">
        <main className="application-status-page">
          <section
            className="authentication-panel application-status-panel"
            aria-labelledby="workspace-selection-title"
          >
            <ProductIdentity />
            <div className="application-status-content">
              <h1 id="workspace-selection-title">Choose Workspace</h1>
              <p>Select the workspace you want to open.</p>
              <WorkspaceSelector
                context={workspace}
                required
                onSelected={(nextWorkspace) =>
                  setSession((current) =>
                    current ? { ...current, workspace: nextWorkspace } : current,
                  )
                }
              />
              <div className="application-status-actions">
                <button className="button button--quiet" type="button" onClick={signOut}>
                  Sign Out
                </button>
              </div>
            </div>
          </section>
        </main>
      </div>
    )
  }

  const activeMembership = workspace.memberships.find(
    (membership) => membership.workspace_id === workspace.active_workspace_id,
  )
  if (!activeMembership) {
    return <ApplicationStatus kind="access-denied" onSignOut={signOut} />
  }
  if (activeMembership.role === 'member') {
    return <ApplicationStatus kind="member" onSignOut={signOut} />
  }

  return (
    <ApplicationWorkspace
      key={workspace.active_workspace_id}
      user={session.user ?? undefined}
      onSignOut={signOut}
      signOutError={signOutError}
      workspace={workspace}
      onWorkspaceSelected={(nextWorkspace) =>
        setSession((current) => (current ? { ...current, workspace: nextWorkspace } : current))
      }
    />
  )
}
