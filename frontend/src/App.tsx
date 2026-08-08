import { ConsultantDirectory } from './consultants/ConsultantDirectory'
import { AppIcon } from './system/AppIcon'
import { HealthStatus } from './system/HealthStatus'

export function App() {
  return (
    <div className="application-frame">
      <header className="application-titlebar">
        <div className="titlebar-brand">
          <AppIcon name="brand" />
          <h1>Leave Planner</h1>
        </div>
      </header>

      <div className="application-shell">
        <aside className="application-rail">
          <div className="brand" aria-hidden="true">
            <AppIcon name="brand" />
          </div>

          <nav className="primary-navigation" aria-label="Primary navigation">
            <button
              className="navigation-item navigation-item--active"
              type="button"
              title="Consultants"
              aria-current="page"
            >
              <AppIcon name="consultants" />
              <span className="visually-hidden">Consultants</span>
            </button>
            <button className="navigation-item" type="button" title="Wallchart" disabled>
              <AppIcon name="wallchart" />
              <span className="visually-hidden">Wallchart</span>
            </button>
            <button className="navigation-item" type="button" title="Settings" disabled>
              <AppIcon name="settings" />
              <span className="visually-hidden">Settings</span>
            </button>
          </nav>

          <HealthStatus />
        </aside>

        <main className="application-content">
          <ConsultantDirectory />
        </main>
      </div>
    </div>
  )
}
