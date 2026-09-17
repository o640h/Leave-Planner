import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PolicySettingsPage } from './PolicySettingsPage'

const documents = [
  {
    document_id: 'hr78-v3',
    document_type: 'Policy',
    title: 'HR.78 Medical & Dental Staff Annual Leave Policy',
    version: '3',
    effective_date: '2025-07-01',
    filename: 'HR78-Medical-Dental-Annual-Leave-Policy-v3.pdf',
  },
  {
    document_id: 'hrs09-v1',
    document_type: 'Guidance',
    title: 'HR.S.09 Annual Leave Guidance for Medical & Dental Staff',
    version: '1',
    effective_date: '2025-07-01',
    filename: 'HRS09-Medical-Dental-Annual-Leave-Guidance-v1.pdf',
  },
]

describe('policy settings page', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('lists document metadata and downloads by stable document id', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:policy')
    const revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(documents), {
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(new Blob(['%PDF-1.4\ntest']), {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition':
              'attachment; filename="HR78-Medical-Dental-Annual-Leave-Policy-v3.pdf"',
          },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    render(<PolicySettingsPage />)

    expect(
      await screen.findByText('HR.78 Medical & Dental Staff Annual Leave Policy'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('HR.S.09 Annual Leave Guidance for Medical & Dental Staff'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('July 2025')).toHaveLength(2)

    fireEvent.click(screen.getAllByRole('button', { name: 'Download PDF' })[0])

    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce())
    expect(fetchMock).toHaveBeenLastCalledWith('/api/policies/hr78-v3/download', {
      credentials: 'same-origin',
    })
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:policy')
  })
})
