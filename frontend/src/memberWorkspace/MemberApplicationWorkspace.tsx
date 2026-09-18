import { useEffect, useState } from 'react'

import { AccountDialog } from '../account/AccountPage'
import { operatorErrorMessage } from '../api/client'
import type { AuthenticatedUser, WorkspaceContext } from '../authentication/types'
import type { PolicyDocument } from '../policies/types'
import { SettingsPage } from '../settings/SettingsPage'
import { AppIcon } from '../system/AppIcon'
import { HealthStatus } from '../system/HealthStatus'
import { WorkspaceFrame } from '../system/WorkspaceFrame'
import { WorkspaceSelectionDialog } from '../workspaces/WorkspaceSelectionDialog'
import { MemberOverview } from './MemberOverview'
import { MemberWallchart } from './MemberWallchart'
import { getMemberWorkspace } from './api'
import type { MemberWallchart as MemberWallchartData, MemberWorkspaceData } from './types'
import './memberWorkspace.css'

const layersIconUrl = '/layers-2.svg'
type MemberPage = 'overview' | 'planning' | 'settings'

type MemberApplicationWorkspaceProps = {
  user: AuthenticatedUser
  workspace: WorkspaceContext
  onSignOut: () => void
  signOutError?: string | null
  onWorkspaceSelected: (context: WorkspaceContext) => void
  onCreateWorkspace: () => void
  initialData?: MemberWorkspaceData
  initialPolicyDocuments?: PolicyDocument[]
  initialWallchart?: MemberWallchartData
}

export function MemberApplicationWorkspace({
  user,
  workspace,
  onSignOut,
  signOutError,
  onWorkspaceSelected,
  onCreateWorkspace,
  initialData,
  initialPolicyDocuments,
  initialWallchart,
}: MemberApplicationWorkspaceProps) {
  const [page, setPage] = useState<MemberPage>('overview')
  const [data, setData] = useState<MemberWorkspaceData | null>(initialData ?? null)
  const [error, setError] = useState<string | null>(null)
  const [loadingYear, setLoadingYear] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountCloseRequested, setAccountCloseRequested] = useState(false)
  const [workspaceSelectionOpen, setWorkspaceSelectionOpen] = useState(false)
  const [workspaceSelectionCloseRequested, setWorkspaceSelectionCloseRequested] = useState(false)

  useEffect(() => {
    if (initialData) return
    let active = true
    getMemberWorkspace()
      .then((result) => {
        if (active) setData(result)
      })
      .catch((reason: unknown) => {
        if (active) setError(operatorErrorMessage(reason))
      })
    return () => {
      active = false
    }
  }, [initialData])

  async function selectLeaveYear(leaveYearId: number) {
    setLoadingYear(true)
    setError(null)
    try {
      setData(await getMemberWorkspace(leaveYearId))
    } catch (reason) {
      setError(operatorErrorMessage(reason))
    } finally {
      setLoadingYear(false)
    }
  }

  const linked = data?.state === 'linked'
  return (
    <WorkspaceFrame>
      <div className="application-shell">
        <aside className="application-rail">
          <div className="brand" aria-hidden="true">
            <AppIcon name="calendar" />
          </div>
          {linked ? (
            <nav className="primary-navigation" aria-label="Primary navigation">
              {(
                [
                  ['overview', 'My Leave', 'profile'],
                  ['planning', 'Team Wallchart', 'wallchart'],
                  ['settings', 'Settings', 'settings'],
                ] as const
              ).map(([target, label, icon]) => (
                <button
                  className={`navigation-item${page === target ? ' navigation-item--active' : ''}`}
                  type="button"
                  title={label}
                  aria-current={page === target ? 'page' : undefined}
                  key={target}
                  onClick={() => setPage(target)}
                >
                  <AppIcon name={icon} />
                  <span className="visually-hidden">{label}</span>
                </button>
              ))}
            </nav>
          ) : null}
          <div className="rail-footer">
            <button
              className={`navigation-item workspace-switcher-control${workspaceSelectionOpen ? ' navigation-item--active' : ''}`}
              type="button"
              title="Switch Workspace"
              aria-expanded={workspaceSelectionOpen}
              onClick={() =>
                workspaceSelectionOpen
                  ? setWorkspaceSelectionCloseRequested(true)
                  : (setWorkspaceSelectionCloseRequested(false), setWorkspaceSelectionOpen(true))
              }
            >
              <img
                className="workspace-switcher-symbol"
                src={layersIconUrl}
                alt=""
                aria-hidden="true"
              />
              <span className="visually-hidden">Switch Workspace</span>
            </button>
            <button
              className={`account-indicator${accountOpen ? ' account-indicator--active' : ''}`}
              type="button"
              title="Account"
              aria-expanded={accountOpen}
              onClick={() =>
                accountOpen
                  ? setAccountCloseRequested(true)
                  : (setAccountCloseRequested(false), setAccountOpen(true))
              }
            >
              <AppIcon name="profile" />
              <span className="visually-hidden">Account</span>
            </button>
            <button
              className="navigation-item"
              type="button"
              title={`Sign Out ${user.display_name}`}
              onClick={onSignOut}
            >
              <AppIcon name="logout" />
              <span className="visually-hidden">Sign Out</span>
            </button>
            {initialData ? null : <HealthStatus />}
          </div>
        </aside>
        <main className="application-content">
          {signOutError ? (
            <p className="application-notice" role="alert">
              {signOutError}
            </p>
          ) : null}
          <div className="application-view">
            {error ? (
              <p className="form-notice form-notice--error member-load-error" role="alert">
                {error}
              </p>
            ) : null}
            {!data ? (
              <div className="member-loading-screen" role="status">
                <AppIcon name="profile" />
                <h2>Loading Your Workspace</h2>
              </div>
            ) : data.state === 'waiting' ? (
              <section className="member-waiting" aria-labelledby="member-waiting-title">
                <AppIcon name="profile" />
                <span className="section-kicker">{data.workspace_name}</span>
                <h1 id="member-waiting-title">Waiting For Consultant Access</h1>
                <p>
                  Your membership is active. A workspace Owner or Admin still needs to link your
                  account to your consultant record.
                </p>
              </section>
            ) : (
              <>
                {page === 'overview' ? (
                  <MemberOverview
                    data={data}
                    loadingYear={loadingYear}
                    onLeaveYearSelected={(id) => void selectLeaveYear(id)}
                  />
                ) : null}
                {page === 'planning' ? <MemberWallchart initialData={initialWallchart} /> : null}
                {page === 'settings' ? (
                  <div className="member-settings-page">
                    <SettingsPage
                      initialSection="policy"
                      availableSections={['policy']}
                      policyDocuments={initialPolicyDocuments}
                    />
                  </div>
                ) : null}
              </>
            )}
          </div>
        </main>
      </div>
      {accountOpen ? (
        <AccountDialog
          user={user}
          closeRequested={accountCloseRequested}
          onClose={() => {
            setAccountOpen(false)
            setAccountCloseRequested(false)
          }}
        />
      ) : null}
      {workspaceSelectionOpen ? (
        <WorkspaceSelectionDialog
          context={workspace}
          closeRequested={workspaceSelectionCloseRequested}
          onClose={() => {
            setWorkspaceSelectionOpen(false)
            setWorkspaceSelectionCloseRequested(false)
          }}
          onSelected={onWorkspaceSelected}
          onCreateWorkspace={onCreateWorkspace}
        />
      ) : null}
    </WorkspaceFrame>
  )
}
