import { AppIcon } from './AppIcon'

export function ProductIdentity() {
  return (
    <div className="authentication-identity">
      <div className="authentication-mark" aria-hidden="true">
        <AppIcon name="calendar" />
      </div>
      <div className="authentication-identity-copy">
        <span className="authentication-company">Merydio</span>
        <h2>Leave Planner</h2>
        <p>Consultant annual leave planning.</p>
      </div>
    </div>
  )
}
