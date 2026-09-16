import { useState } from 'react'

import type { WorkspaceContext } from '../authentication/types'
import { HolidaySettingsPage } from '../publicHolidays/HolidaySettingsPage'
import { AppIcon } from '../system/AppIcon'
import { WorkspaceManagement } from '../workspaces/WorkspaceManagement'
import { getThemePreference, saveThemePreference } from './theme'
import type { ThemePreference } from './theme'
import './settings.css'

type SettingsSection = 'workspace' | 'appearance' | 'public-holidays'

const sections = [
  { id: 'workspace', label: 'Workspace', icon: 'profile' },
  { id: 'appearance', label: 'Appearance', icon: 'appearance' },
  { id: 'public-holidays', label: 'Public Holidays', icon: 'calendar' },
] as const

type SettingsPageProps = {
  workspace?: WorkspaceContext
  onCreateWorkspace?: () => void
  onWorkspaceContextChanged?: (context: WorkspaceContext) => void
}

function AppearanceSettings() {
  const [theme, setTheme] = useState<ThemePreference>(getThemePreference)

  function selectTheme(nextTheme: ThemePreference) {
    setTheme(nextTheme)
    saveThemePreference(nextTheme)
  }

  return (
    <section className="settings-section" aria-labelledby="appearance-title">
      <header className="settings-content-heading">
        <span className="section-label">Interface</span>
        <h2 id="appearance-title">Appearance</h2>
      </header>

      <section className="settings-panel appearance-panel">
        <header>
          <div>
            <h3>Theme</h3>
            <p>Choose how Leave Planner is displayed.</p>
          </div>
        </header>
        <div className="theme-options" role="group" aria-label="Theme">
          <button
            className={`theme-option${theme === 'dark' ? ' theme-option--selected' : ''}`}
            type="button"
            aria-pressed={theme === 'dark'}
            onClick={() => selectTheme('dark')}
          >
            <span className="theme-preview theme-preview--dark" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>
              <strong>Dark</strong>
              <small>{theme === 'dark' ? 'Selected' : ''}</small>
            </span>
          </button>
          <button
            className={`theme-option${theme === 'light' ? ' theme-option--selected' : ''}`}
            type="button"
            aria-pressed={theme === 'light'}
            onClick={() => selectTheme('light')}
          >
            <span className="theme-preview theme-preview--light" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>
              <strong>Light</strong>
              <small>{theme === 'light' ? 'Selected' : ''}</small>
            </span>
          </button>
          <button
            className={`theme-option${theme === 'system' ? ' theme-option--selected' : ''}`}
            type="button"
            aria-pressed={theme === 'system'}
            onClick={() => selectTheme('system')}
          >
            <span className="theme-preview theme-preview--system" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>
              <strong>System</strong>
              <small>{theme === 'system' ? 'Selected' : ''}</small>
            </span>
          </button>
        </div>
      </section>
    </section>
  )
}

export function SettingsPage({
  workspace,
  onCreateWorkspace,
  onWorkspaceContextChanged,
}: SettingsPageProps) {
  const [activeSection, setActiveSection] = useState<SettingsSection>('workspace')

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
        {activeSection === 'appearance' ? <AppearanceSettings /> : null}
        {activeSection === 'public-holidays' ? <HolidaySettingsPage /> : null}
      </div>
    </section>
  )
}
