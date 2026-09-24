import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { WorkspaceFrame } from './WorkspaceFrame'

describe('workspace sizing', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('fills the browser and restores the bounded workspace without replacing its contents', async () => {
    const user = userEvent.setup()
    render(
      <WorkspaceFrame>
        <input aria-label="Unsaved Note" />
      </WorkspaceFrame>,
    )
    await user.type(screen.getByRole('textbox'), 'Keep this')
    await user.click(screen.getByRole('button', { name: 'Fill Window' }))
    expect(screen.getByRole('button', { name: 'Resize Workspace' })).toBeDisabled()
    expect(screen.getByRole('textbox')).toHaveValue('Keep this')
    await user.click(screen.getByRole('button', { name: 'Restore Size' }))
    expect(screen.getByRole('button', { name: 'Resize Workspace' })).toBeEnabled()
  })

  it('allows keyboard resizing and clamps it to the usable minimum', () => {
    const { container } = render(<WorkspaceFrame>Content</WorkspaceFrame>)
    const handle = screen.getByRole('button', { name: 'Resize Workspace' })
    fireEvent.keyDown(handle, { key: 'ArrowLeft' })
    expect(container.firstChild).toHaveStyle('width: 720px')
    fireEvent.keyDown(handle, { key: 'ArrowUp' })
    expect(container.firstChild).toHaveStyle('height: 480px')
  })

  it('keeps resized height within the space reserved for the footer', () => {
    vi.stubGlobal('innerHeight', 900)
    const { container } = render(
      <div style={{ paddingTop: 56, paddingBottom: 56 }}>
        <WorkspaceFrame>Content</WorkspaceFrame>
      </div>,
    )
    const frame = container.querySelector('.workspace-frame') as HTMLDivElement
    expect(frame).toHaveStyle('height: 788px')

    vi.spyOn(frame, 'getBoundingClientRect').mockReturnValue({
      width: 1024,
      height: 788,
    } as DOMRect)
    fireEvent.keyDown(screen.getByRole('button', { name: 'Resize Workspace' }), {
      key: 'ArrowDown',
    })
    expect(frame).toHaveStyle('height: 788px')
  })
})
