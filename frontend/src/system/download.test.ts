import { afterEach, expect, it, vi } from 'vitest'

import { downloadFile } from './download'

afterEach(() => {
  vi.restoreAllMocks()
})

it('starts a browser download with the server-provided filename', () => {
  const createObjectURL = vi.fn().mockReturnValue('blob:leave-log')
  const revokeObjectURL = vi.fn()
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
  const blob = new Blob(['leave log'], { type: 'application/pdf' })

  downloadFile(blob, 'Consultant_Leave_Log.pdf')

  expect(createObjectURL).toHaveBeenCalledWith(blob)
  expect(click).toHaveBeenCalledOnce()
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:leave-log')
  expect(document.querySelector('a[download]')).not.toBeInTheDocument()
})
