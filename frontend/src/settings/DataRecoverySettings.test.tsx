import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DataRecoverySettings } from './DataRecoverySettings'

const emptyStatus = {
  data_directory: 'C:\\Users\\Operator\\AppData\\Local\\LeavePlanner',
  backup_directory: 'C:\\Users\\Operator\\AppData\\Local\\LeavePlanner\\backups',
  latest_automatic_backup_at: null,
  backups: [],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DataRecoverySettings', () => {
  it('creates a manual backup and refreshes the verified backup list', async () => {
    const user = userEvent.setup()
    const manualBackup = {
      name: 'leave-planner-manual-20260815T120000Z.sqlite3',
      kind: 'manual',
      created_at: '2026-08-15T12:00:00Z',
      size_bytes: 2 * 1024 * 1024,
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(emptyStatus))
      .mockResolvedValueOnce(
        Response.json({ message: `${manualBackup.name} was created and verified.` }),
      )
      .mockResolvedValueOnce(Response.json({ ...emptyStatus, backups: [manualBackup] }))
    vi.stubGlobal('fetch', fetchMock)

    render(<DataRecoverySettings />)

    await screen.findByText('No backups have been created yet.')
    expect(screen.getByText('Latest Automatic Backup')).toBeVisible()
    expect(screen.getByText('Not Created Yet')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Create Backup' }))

    expect(await screen.findByText('Manual Backup')).toBeVisible()
    expect(screen.getByText('2.0 MB')).toBeVisible()
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/settings/recovery/backups',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('requires the exact restore confirmation before enabling restore', async () => {
    const user = userEvent.setup()
    const backup = {
      name: 'leave-planner-manual-20260815T120000Z.sqlite3',
      kind: 'manual',
      created_at: '2026-08-15T12:00:00Z',
      size_bytes: 1024,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ ...emptyStatus, backups: [backup] })),
    )

    render(<DataRecoverySettings />)

    await user.click(await screen.findByRole('button', { name: 'Restore' }))
    const confirmation = screen.getByRole('textbox')
    const restore = screen.getByRole('button', { name: 'Restore Backup' })

    expect(restore).toBeDisabled()
    await user.type(confirmation, 'restore')
    expect(restore).toBeDisabled()
    await user.clear(confirmation)
    await user.type(confirmation, 'RESTORE')

    await waitFor(() => expect(restore).toBeEnabled())
  })
})
