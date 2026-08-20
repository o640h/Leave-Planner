import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApplicationWorkspace } from '../App'
import { CarryForwardControl } from '../carryForward/CarryForwardControl'

function json(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body) }
}

describe('holiday and carry-forward workflows', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('opens the shared public-holiday settings from primary navigation', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/consultants') return Promise.resolve(json([]))
        if (path === '/api/settings/public-holidays') {
          return Promise.resolve(
            json({
              source: 'static_snapshot',
              source_date: '2026-08-06',
              holidays: [{ holiday_date: '2026-12-25', name: 'Christmas Day', notes: '' }],
              corrections: [],
            }),
          )
        }
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    render(<ApplicationWorkspace />)
    await user.click(screen.getByRole('button', { name: 'Settings' }))
    await user.click(screen.getByRole('button', { name: 'Public Holidays' }))
    expect(await screen.findByRole('heading', { name: 'Public Holidays' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /2026/ })).toBeInTheDocument()
    expect(screen.getByText('1 Date')).toBeInTheDocument()
  })

  it('adds workbook carry-forward and shows its calculated total', async () => {
    const user = userEvent.setup()
    let saved = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, options: RequestInit = {}) => {
        if ((options.method ?? 'GET') === 'GET') {
          return json({
            id: null,
            leave_year_id: 1,
            dcc_hours: '0',
            spa_hours: '0',
            total_hours: '0',
            created_at: null,
          })
        }
        saved = true
        return json({
          id: 1,
          leave_year_id: 1,
          dcc_hours: '41.25',
          spa_hours: '3.5',
          total_hours: '44.75',
          created_at: '2026-08-10T12:00:00',
        })
      }),
    )

    render(<CarryForwardControl consultantId={1} leaveYearId={1} />)
    await user.click(screen.getByRole('button', { name: 'Add' }))
    const dialog = screen.getByRole('dialog', { name: 'Carry Forward' })
    const dccCarryForward = within(dialog).getByLabelText('DCC Hours')
    const spaCarryForward = within(dialog).getByLabelText('SPA Hours')
    await user.clear(dccCarryForward)
    await user.type(dccCarryForward, '41.25')
    await user.clear(spaCarryForward)
    await user.type(spaCarryForward, '3.5')
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    expect(saved).toBe(true)
    expect(await screen.findByText('41.25')).toBeInTheDocument()
    expect(screen.getByText('3.5')).toBeInTheDocument()
    expect(screen.getByText('DCC')).toBeInTheDocument()
    expect(screen.getByText('SPA')).toBeInTheDocument()
  })
})
