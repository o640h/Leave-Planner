import { useEffect, useState } from 'react'

import {
  AUTHENTICATION_REQUIRED_EVENT,
  AUTHORIZATION_DENIED_EVENT,
  SERVICE_UNAVAILABLE_EVENT,
} from './api/client'
import { getRegistrationConfiguration, getSession, logout } from './authentication/api'
import { AccountActionScreen, type AccountActionMode } from './authentication/AccountActionScreen'
import { LoginScreen } from './authentication/LoginScreen'
import { RegistrationScreen } from './authentication/RegistrationScreen'
import type {
  AuthenticatedUser,
  RegistrationMode,
  Session,
  WorkspaceContext,
} from './authentication/types'
import { ConsultantDirectory } from './consultants/ConsultantDirectory'
import { PlanningPage } from './planning/PlanningPage'
import { SettingsPage } from './settings/SettingsPage'
import { AppIcon } from './system/AppIcon'
import { HealthStatus } from './system/HealthStatus'
import { ProductIdentity } from './system/ProductIdentity'
import { WorkspaceFrame } from './system/WorkspaceFrame'
import { WorkspaceCreationDialog } from './workspaces/WorkspaceCreationDialog'
import { WorkspaceSelector } from './workspaces/WorkspaceSelector'

type ApplicationWorkspaceProps = {
  user?: AuthenticatedUser
  onSignOut?: () => void
  signOutError?: string | null
  workspace?: WorkspaceContext
  onWorkspaceSelected?: (context: WorkspaceContext) => void
  onManageAccount?: () => void
  onCreateWorkspace?: () => void
}

export function ApplicationWorkspace({
  user,
  onSignOut,
  signOutError,
  workspace,
  onWorkspaceSelected,
  onManageAccount,
  onCreateWorkspace,
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
              <button
                className="account-indicator"
                type="button"
                title={`Change Email For ${user.display_name}`}
                onClick={onManageAccount}
              >
                <AppIcon name="profile" />
                <span className="visually-hidden">Change Email For {user.display_name}</span>
              </button>
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
          {page === 'settings' && (
            <SettingsPage workspace={workspace} onCreateWorkspace={onCreateWorkspace} />
          )}
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
  onManageAccount?: () => void
  onCreateWorkspace?: () => void
}

function ApplicationStatus({
  kind,
  busy = false,
  onRetry,
  onSignOut,
  onManageAccount,
  onCreateWorkspace,
}: ApplicationStatusProps) {
  const unavailable = kind === 'unavailable'
  const title = unavailable
    ? 'Server Unavailable'
    : kind === 'onboarding'
      ? 'No Workspace Yet'
      : kind === 'member'
        ? 'Member Workspace'
        : 'Workspace Access Unavailable'
  const message = unavailable
    ? 'Leave Planner could not reach the server. Check the connection and try again.'
    : kind === 'onboarding'
      ? 'This account does not currently belong to a workspace. You can create one now or sign out.'
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
              {onCreateWorkspace ? (
                <button
                  className="button button--primary"
                  type="button"
                  onClick={onCreateWorkspace}
                >
                  Create Workspace
                </button>
              ) : null}
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
              {onManageAccount ? (
                <button className="button button--quiet" type="button" onClick={onManageAccount}>
                  Change Email
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
  const [registrationMode, setRegistrationMode] = useState<RegistrationMode>('invitation_only')
  const [registrationOpen, setRegistrationOpen] = useState(false)
  const [workspaceCreationOpen, setWorkspaceCreationOpen] = useState(false)
  const [applicationState, setApplicationState] = useState<
    'ready' | 'access-denied' | 'unavailable'
  >('ready')
  const [loginNotice, setLoginNotice] = useState<string | null>(null)
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const initialParameters = new URLSearchParams(window.location.search)
  const initialAction = initialParameters.get('action') as AccountActionMode | null
  const [accountAction, setAccountAction] = useState<{
    mode: AccountActionMode
    token?: string
  } | null>(
    initialAction && ['reset-password', 'verify-email', 'confirm-email'].includes(initialAction)
      ? { mode: initialAction, token: initialParameters.get('token') ?? '' }
      : null,
  )

  useEffect(() => {
    let active = true
    Promise.allSettled([getSession(), getRegistrationConfiguration()]).then((results) => {
      const [sessionResult, registrationResult] = results
      if (!active) return
      if (registrationResult.status === 'fulfilled') {
        setRegistrationMode(registrationResult.value.mode)
      }
      if (sessionResult.status === 'fulfilled') {
        const nextSession = sessionResult.value
        setSession(nextSession)
        setApplicationState('ready')
      } else {
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
      const [sessionResult, registrationResult] = await Promise.allSettled([
        getSession(),
        getRegistrationConfiguration(),
      ])
      if (sessionResult.status === 'rejected') throw sessionResult.reason
      setSession(sessionResult.value)
      if (registrationResult.status === 'fulfilled') {
        setRegistrationMode(registrationResult.value.mode)
      }
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

  function closeAccountAction(notice?: string) {
    const completedCredentialAction =
      accountAction?.mode === 'reset-password' || accountAction?.mode === 'confirm-email'
    window.history.replaceState({}, '', window.location.pathname)
    setAccountAction(null)
    if (notice) setLoginNotice(notice)
    if (completedCredentialAction) {
      setSession({ authenticated: false, user: null, workspace: null })
    }
  }

  function workspaceCreated(context: WorkspaceContext) {
    setSession((current) => (current ? { ...current, workspace: context } : current))
    setWorkspaceCreationOpen(false)
  }

  if (accountAction) {
    return (
      <AccountActionScreen
        mode={accountAction.mode}
        token={accountAction.token}
        currentEmail={
          accountAction.mode === 'change-email'
            ? (session?.user?.display_email ?? undefined)
            : undefined
        }
        onBack={closeAccountAction}
      />
    )
  }

  if (applicationState === 'unavailable') {
    return <ApplicationStatus kind="unavailable" busy={retrying} onRetry={retryConnection} />
  }

  if (registrationOpen) {
    return (
      <RegistrationScreen
        onBack={(notice) => {
          setRegistrationOpen(false)
          if (notice) setLoginNotice(notice)
        }}
      />
    )
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
        onForgotPassword={() => setAccountAction({ mode: 'forgot-password' })}
        onRegister={registrationMode === 'open' ? () => setRegistrationOpen(true) : undefined}
      />
    )
  }

  const workspace = session.workspace
  if (!workspace || workspace.state === 'onboarding') {
    return (
      <>
        <ApplicationStatus
          kind="onboarding"
          onCreateWorkspace={() => setWorkspaceCreationOpen(true)}
          onSignOut={signOut}
          onManageAccount={() => setAccountAction({ mode: 'change-email' })}
        />
        {workspaceCreationOpen ? (
          <WorkspaceCreationDialog
            onCancel={() => setWorkspaceCreationOpen(false)}
            onCreated={workspaceCreated}
          />
        ) : null}
      </>
    )
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
    return (
      <ApplicationStatus
        kind="access-denied"
        onSignOut={signOut}
        onManageAccount={() => setAccountAction({ mode: 'change-email' })}
      />
    )
  }
  if (activeMembership.role === 'member') {
    return (
      <>
        <ApplicationStatus
          kind="member"
          onCreateWorkspace={() => setWorkspaceCreationOpen(true)}
          onSignOut={signOut}
          onManageAccount={() => setAccountAction({ mode: 'change-email' })}
        />
        {workspaceCreationOpen ? (
          <WorkspaceCreationDialog
            onCancel={() => setWorkspaceCreationOpen(false)}
            onCreated={workspaceCreated}
          />
        ) : null}
      </>
    )
  }

  return (
    <>
      <ApplicationWorkspace
        key={workspace.active_workspace_id}
        user={session.user ?? undefined}
        onSignOut={signOut}
        signOutError={signOutError}
        workspace={workspace}
        onWorkspaceSelected={(nextWorkspace) =>
          setSession((current) => (current ? { ...current, workspace: nextWorkspace } : current))
        }
        onManageAccount={() => setAccountAction({ mode: 'change-email' })}
        onCreateWorkspace={() => setWorkspaceCreationOpen(true)}
      />
      {workspaceCreationOpen ? (
        <WorkspaceCreationDialog
          onCancel={() => setWorkspaceCreationOpen(false)}
          onCreated={workspaceCreated}
        />
      ) : null}
    </>
  )
}
