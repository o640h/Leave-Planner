import { useState } from 'react'

import type { WorkspaceContext } from '../authentication/types'
import { PolicySettingsPage } from '../policies/PolicySettingsPage'
import { HolidaySettingsPage } from '../publicHolidays/HolidaySettingsPage'
import { AppIcon } from '../system/AppIcon'
import { WorkspaceManagement } from '../workspaces/WorkspaceManagement'
import './settings.css'

export type SettingsSection = 'workspace' | 'public-holidays' | 'policy'

const sections = [
  { id: 'workspace', label: 'Workspace', icon: 'profile' },
  { id: 'public-holidays', label: 'Public Holidays', icon: 'calendar' },
  { id: 'policy', label: 'Policy & Guidance', icon: 'document' },
] as const

type SettingsPageProps = {
  workspace?: WorkspaceContext
  onCreateWorkspace?: () => void
  onWorkspaceContextChanged?: (context: WorkspaceContext) => void
  initialSection?: SettingsSection
}

export function SettingsPage({
  workspace,
  onCreateWorkspace,
  onWorkspaceContextChanged,
  initialSection = 'workspace',
}: SettingsPageProps) {
  const [activeSection, setActiveSection] = useState<SettingsSection>(initialSection)

  return (
    <section className="settings-workspace" aria-label="Settings">
      <aside className="settings-directory">
        <header>
          <span className="section-label">Application</span>
          <h2>Settings</h2>
        </header>
        <nav aria-label="Settings Categories">
          {sections.map((section) => (
            <button
              className={`settings-category${
                activeSection === section.id ? ' settings-category--active' : ''
              }`}
              type="button"
              key={section.id}
              aria-current={activeSection === section.id ? 'page' : undefined}
              onClick={() => setActiveSection(section.id)}
            >
              <AppIcon name={section.icon} />
              <span>{section.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="settings-content">
        {activeSection === 'workspace' ? (
          onCreateWorkspace && onWorkspaceContextChanged ? (
            <WorkspaceManagement
              activeWorkspaceId={workspace?.active_workspace_id ?? null}
              onCreateWorkspace={onCreateWorkspace}
              onWorkspaceContextChanged={onWorkspaceContextChanged}
            />
          ) : (
            <section className="settings-section" aria-labelledby="workspace-settings-title">
              <header className="settings-content-heading">
                <span className="section-label">Account Access</span>
                <h2 id="workspace-settings-title">Workspaces</h2>
              </header>
            </section>
          )
        ) : null}
        {activeSection === 'public-holidays' ? <HolidaySettingsPage /> : null}
        {activeSection === 'policy' ? <PolicySettingsPage /> : null}
      </div>
    </section>
  )
}
