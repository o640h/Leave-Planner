import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { WorkspaceFrame } from './WorkspaceFrame'

describe('workspace sizing', () => {
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
})
