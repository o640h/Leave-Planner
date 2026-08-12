import { useState } from 'react'

import { ConsultantDirectory } from './consultants/ConsultantDirectory'
import { PlanningPage } from './planning/PlanningPage'
import { SettingsPage } from './settings/SettingsPage'
import { AppIcon } from './system/AppIcon'
import { HealthStatus } from './system/HealthStatus'

export function App() {
  const [page, setPage] = useState<'consultants' | 'planning' | 'settings'>('consultants')
  const desktopHost = new URLSearchParams(window.location.search).get('desktop') === '1'

  return (
    <div className={`application-frame${desktopHost ? ' application-frame--desktop' : ''}`}>
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

          <HealthStatus />
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
