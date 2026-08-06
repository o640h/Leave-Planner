import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

describe('App', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows that the local service is ready after a successful health check', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: 'ok' }) }),
    )

    render(<App />)

    expect(screen.getByRole('heading', { name: 'Leave Planner' })).toBeInTheDocument()
    expect(await screen.findByText('Local service ready')).toBeInTheDocument()
  })
})
