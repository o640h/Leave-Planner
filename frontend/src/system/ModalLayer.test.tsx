import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { ModalLayer } from './ModalLayer'

function DialogHarness() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open Editor
      </button>
      {open ? (
        <ModalLayer onClose={() => setOpen(false)}>
          <div className="modal-backdrop">
            <section role="dialog" aria-modal="true" aria-labelledby="editor-title" tabIndex={-1}>
              <h2 id="editor-title">Example Editor</h2>
              <button type="button">First Action</button>
              <button type="button">Last Action</button>
            </section>
          </div>
        </ModalLayer>
      ) : null}
    </>
  )
}

it('keeps keyboard focus inside an open dialog', async () => {
  const user = userEvent.setup()
  render(<DialogHarness />)

  await user.click(screen.getByRole('button', { name: 'Open Editor' }))
  const dialog = screen.getByRole('dialog', { name: 'Example Editor' })

  // Opening a rich editor focuses its labelled container so assistive technology announces it.
  expect(dialog).toHaveFocus()
  await user.tab()
  expect(screen.getByRole('button', { name: 'First Action' })).toHaveFocus()
  await user.tab({ shift: true })
  expect(screen.getByRole('button', { name: 'Last Action' })).toHaveFocus()
})

it('closes with Escape and restores focus to the control that opened it', async () => {
  const user = userEvent.setup()
  render(<DialogHarness />)
  const opener = screen.getByRole('button', { name: 'Open Editor' })

  await user.click(opener)
  await user.keyboard('{Escape}')

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(opener).toHaveFocus()
})
