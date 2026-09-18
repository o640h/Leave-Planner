import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { UiCatalogue } from './UiCatalogue'
import { uiCatalogueEntries } from './uiCatalogueEntries'

function json(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body) }
}

describe('development UI catalogue', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists every registered preview from one index', () => {
    render(<UiCatalogue pathname="/ui" />)

    expect(screen.getByRole('heading', { name: 'UI Catalogue' })).toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(uiCatalogueEntries.length)
    expect(screen.getByRole('link', { name: /Server Unavailable/ })).toHaveAttribute(
      'href',
      '/ui/server-unavailable',
    )
    expect(screen.queryByRole('link', { name: /Appearance Settings/ })).not.toBeInTheDocument()
  })

  it('opens account and application-state previews directly', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(json({ status: 'ok' }))),
    )
    const { rerender } = render(<UiCatalogue pathname="/ui/login" />)
    expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()

    rerender(<UiCatalogue pathname="/ui/server-unavailable" />)
    expect(screen.getByRole('heading', { name: 'Server Unavailable' })).toBeInTheDocument()
  })

  it('opens the seeded Member workspace without a backend session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(json({ status: 'ok' }))),
    )

    render(<UiCatalogue pathname="/ui/member" />)

    expect(screen.getByRole('heading', { name: 'Alex Morgan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.queryByText('Leave Setup Status')).not.toBeInTheDocument()
  })
})
