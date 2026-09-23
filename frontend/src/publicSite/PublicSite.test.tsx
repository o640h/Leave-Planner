import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { PublicShell } from './PublicSite'

describe('public information', () => {
  afterEach(() => {
    window.history.replaceState({}, '', '/')
    vi.unstubAllGlobals()
  })

  it('opens a standalone privacy page without requesting a session', () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    window.history.replaceState({}, '', '/privacy')

    render(<App />)

    expect(screen.getByRole('heading', { name: 'Privacy' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back To App' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: 'Contact' })).toHaveAttribute('href', '/contact')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('keeps information links outside the application frame', () => {
    const { container } = render(
      <PublicShell>
        <div className="application-frame">Sign In</div>
      </PublicShell>,
    )

    const frame = container.querySelector('.application-frame')!
    const footer = container.querySelector('.site-footer')!
    expect(frame.contains(footer)).toBe(false)
    expect(screen.getByRole('link', { name: 'Terms' })).toHaveAttribute('href', '/terms')
  })
})
