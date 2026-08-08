import { useEffect, useState } from 'react'

import { apiRequest } from '../api/client'

type Health = {
  status: string
}

type ServiceState = 'checking' | 'ready' | 'unavailable'

export function HealthStatus() {
  const [health, setHealth] = useState<ServiceState>('checking')

  useEffect(() => {
    apiRequest<Health>('/api/health')
      .then((result) => {
        setHealth(result.status === 'ok' ? 'ready' : 'unavailable')
      })
      .catch(() => {
        setHealth('unavailable')
      })
  }, [])

  return (
    <div className={`service-state service-state--${health}`} aria-live="polite">
      <span aria-hidden="true" />
      <div>
        <small>Local Service</small>
        <strong>
          {health === 'checking' ? 'Connecting' : health === 'ready' ? 'Ready' : 'Unavailable'}
        </strong>
      </div>
    </div>
  )
}
