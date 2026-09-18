import type { FormEvent, ReactNode } from 'react'

import {
  ApplicationLoading,
  ApplicationStatus,
  ApplicationWorkspace,
  WorkspaceSelectionScreen,
  type ApplicationPage,
} from '../App'
import { AccountActionScreen, type AccountActionMode } from '../authentication/AccountActionScreen'
import { LoginScreen } from '../authentication/LoginScreen'
import { RegistrationScreen } from '../authentication/RegistrationScreen'
import type { AuthenticatedUser, WorkspaceContext } from '../authentication/types'
import { MemberApplicationWorkspace } from '../memberWorkspace/MemberApplicationWorkspace'
import type { SettingsSection } from '../settings/SettingsPage'
import { WorkspaceCreationDialog } from '../workspaces/WorkspaceCreationDialog'
import {
  memberPreviewData,
  memberPreviewPolicyDocuments,
  memberPreviewWallchart,
} from './memberPreviewData'
import { type CatalogueGroup, uiCatalogueEntries } from './uiCatalogueEntries'
import './uiCatalogue.css'

const previewUser: AuthenticatedUser = {
  public_id: 'ui-preview-account',
  display_name: 'Preview Operator',
  display_email: 'operator@example.com',
}

const previewWorkspace: WorkspaceContext = {
  state: 'active',
  active_workspace_id: 1,
  memberships: [
    {
      workspace_id: 1,
      workspace_name: 'Consultants',
      role: 'owner',
      linked_consultant_id: null,
    },
    {
      workspace_id: 2,
      workspace_name: 'Quality Assurance',
      role: 'admin',
      linked_consultant_id: null,
    },
  ],
}

const selectionWorkspace: WorkspaceContext = {
  ...previewWorkspace,
  state: 'selection_required',
}

const previewMemberWorkspace: WorkspaceContext = {
  state: 'active',
  active_workspace_id: 1,
  memberships: [
    {
      workspace_id: 1,
      workspace_name: 'Consultants',
      role: 'member',
      linked_consultant_id: 1,
    },
  ],
}

const noop = () => undefined

function StaticFormPreview({ children }: { children: ReactNode }) {
  function preventSubmission(event: FormEvent<HTMLDivElement>) {
    event.preventDefault()
    event.stopPropagation()
  }

  return (
    <div className="ui-catalogue-static-preview" onSubmitCapture={preventSubmission}>
      {children}
    </div>
  )
}

function AccountActionPreview({ mode }: { mode: AccountActionMode }) {
  return (
    <StaticFormPreview>
      <AccountActionScreen
        mode={mode}
        token="ui-preview-token"
        currentEmail={mode === 'change-email' ? previewUser.display_email : undefined}
        onBack={noop}
      />
    </StaticFormPreview>
  )
}

function WorkspacePreview({
  page,
  settingsSection,
  initialAccountOpen,
}: {
  page: ApplicationPage
  settingsSection?: SettingsSection
  initialAccountOpen?: boolean
}) {
  return (
    <ApplicationWorkspace
      user={previewUser}
      workspace={previewWorkspace}
      initialPage={page}
      initialSettingsSection={settingsSection}
      initialAccountOpen={initialAccountOpen}
      onSignOut={noop}
      onCreateWorkspace={noop}
      onWorkspaceSelected={noop}
    />
  )
}

function CatalogueIndex() {
  const groups: CatalogueGroup[] = ['Account', 'Application States', 'Workspace']
  return (
    <main className="ui-catalogue" aria-labelledby="ui-catalogue-title">
      <header className="ui-catalogue-heading">
        <div>
          <span className="section-label">Development Only</span>
          <h1 id="ui-catalogue-title">UI Catalogue</h1>
        </div>
        <p>
          Open every current application surface directly while checking visual consistency. Forms
          on account previews are intentionally inert.
        </p>
      </header>

      <div className="ui-catalogue-groups">
        {groups.map((group) => (
          <section className="ui-catalogue-group" key={group} aria-labelledby={`group-${group}`}>
            <h2 id={`group-${group}`}>{group}</h2>
            <div className="ui-catalogue-list">
              {uiCatalogueEntries
                .filter((entry) => entry.group === group)
                .map((entry) => (
                  <a className="ui-catalogue-entry" href={entry.path} key={entry.path}>
                    <span>
                      <strong>{entry.title}</strong>
                      <small>{entry.path}</small>
                    </span>
                    <span className="ui-catalogue-entry-detail">
                      {entry.description}
                      {entry.usesLiveData ? <em>Uses local account data</em> : null}
                    </span>
                  </a>
                ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  )
}

function UnknownPreview({ pathname }: { pathname: string }) {
  return (
    <main className="ui-catalogue ui-catalogue--unknown">
      <span className="section-label">Development Only</span>
      <h1>Preview Not Found</h1>
      <p>No UI preview is registered for {pathname}.</p>
      <a className="button button--primary" href="/ui">
        Open UI Catalogue
      </a>
    </main>
  )
}

export function UiCatalogue({ pathname = window.location.pathname }: { pathname?: string }) {
  const route = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname

  if (route === '/ui') return <CatalogueIndex />
  if (route === '/ui/login') {
    return (
      <StaticFormPreview>
        <LoginScreen onAuthenticated={noop} onForgotPassword={noop} onRegister={noop} />
      </StaticFormPreview>
    )
  }
  if (route === '/ui/register') {
    return (
      <StaticFormPreview>
        <RegistrationScreen onBack={noop} />
      </StaticFormPreview>
    )
  }
  if (route === '/ui/forgot-password') return <AccountActionPreview mode="forgot-password" />
  if (route === '/ui/reset-password') return <AccountActionPreview mode="reset-password" />
  if (route === '/ui/verify-email') return <AccountActionPreview mode="verify-email" />
  if (route === '/ui/confirm-email') return <AccountActionPreview mode="confirm-email" />
  if (route === '/ui/change-email') return <AccountActionPreview mode="change-email" />
  if (route === '/ui/connecting') return <ApplicationLoading />
  if (route === '/ui/server-unavailable') {
    return <ApplicationStatus kind="unavailable" onRetry={noop} />
  }
  if (route === '/ui/access-denied') {
    return <ApplicationStatus kind="access-denied" onSignOut={noop} />
  }
  if (route === '/ui/no-workspace') {
    return (
      <ApplicationStatus
        kind="onboarding"
        onCreateWorkspace={noop}
        onSignOut={noop}
        onManageAccount={noop}
      />
    )
  }
  if (route === '/ui/create-workspace') {
    return (
      <StaticFormPreview>
        <ApplicationStatus
          kind="onboarding"
          onCreateWorkspace={noop}
          onSignOut={noop}
          onManageAccount={noop}
        />
        <WorkspaceCreationDialog onCancel={noop} onCreated={noop} />
      </StaticFormPreview>
    )
  }
  if (route === '/ui/workspace-selection') {
    return (
      <WorkspaceSelectionScreen workspace={selectionWorkspace} onSelected={noop} onSignOut={noop} />
    )
  }
  if (route === '/ui/member') {
    return (
      <MemberApplicationWorkspace
        user={{ ...previewUser, display_name: 'Alex Morgan', display_email: 'alex@example.com' }}
        workspace={previewMemberWorkspace}
        initialData={memberPreviewData}
        initialPolicyDocuments={memberPreviewPolicyDocuments}
        initialWallchart={memberPreviewWallchart}
        onSignOut={noop}
        onWorkspaceSelected={noop}
        onCreateWorkspace={noop}
      />
    )
  }
  if (route === '/ui/consultants') return <WorkspacePreview page="consultants" />
  if (route === '/ui/planning') return <WorkspacePreview page="planning" />
  if (route === '/ui/account') {
    return <WorkspacePreview page="consultants" initialAccountOpen />
  }
  if (route === '/ui/settings/workspace') {
    return <WorkspacePreview page="settings" settingsSection="workspace" />
  }
  if (route === '/ui/settings/public-holidays') {
    return <WorkspacePreview page="settings" settingsSection="public-holidays" />
  }
  if (route === '/ui/settings/policy') {
    return <WorkspacePreview page="settings" settingsSection="policy" />
  }

  return <UnknownPreview pathname={route} />
}
