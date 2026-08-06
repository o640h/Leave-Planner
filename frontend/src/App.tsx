import { useEffect, useState } from 'react'

type Health = { status: string }

export function App() {
  const [health, setHealth] = useState<'checking' | 'ready' | 'unavailable'>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error('Health check failed')
        return response.json() as Promise<Health>
      })
      .then((result) => setHealth(result.status === 'ok' ? 'ready' : 'unavailable'))
      .catch(() => setHealth('unavailable'))
  }, [])

  return (
    <main className="shell">
      <header className="masthead">
        <div>
          <p className="eyebrow">Consultant annual leave</p>
          <h1>Leave Planner</h1>
        </div>
        <span className={`status status--${health}`} aria-live="polite">
          <span aria-hidden="true" />
          {health === 'checking'
            ? 'Connecting'
            : health === 'ready'
              ? 'Local service ready'
              : 'Service unavailable'}
        </span>
      </header>
      <section className="welcome" aria-labelledby="foundation-title">
        <div>
          <p className="eyebrow">Engineering foundation</p>
          <h2 id="foundation-title">One reliable place for the whole team.</h2>
          <p>
            The local application shell is connected. Consultant maintenance, leave calculations,
            planning, and reports will be delivered through the roadmap.
          </p>
        </div>
        <div className="foundation-card">
          <span>Phase 1</span>
          <strong>Foundation</strong>
          <small>React · FastAPI · SQLite</small>
        </div>
      </section>
    </main>
  )
}
