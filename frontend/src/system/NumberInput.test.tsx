import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { NumberInput } from './NumberInput'

function Example({
  initialValue,
  step,
  buttonSteps,
}: {
  initialValue: string
  step: string
  buttonSteps?: number
}) {
  const [value, setValue] = useState(initialValue)
  return (
    <NumberInput
      label="Amount"
      value={value}
      step={step}
      buttonSteps={buttonSteps}
      onChange={setValue}
    />
  )
}

describe('NumberInput', () => {
  it('uses the PA increment supplied by its field', () => {
    render(<Example initialValue="5.91" step="0.01" />)

    fireEvent.click(screen.getByRole('button', { name: 'Increase Amount' }))

    expect(screen.getByRole('spinbutton', { name: 'Amount' })).toHaveValue(5.92)
  })

  it('uses the whole-hour increment supplied by its field', () => {
    render(<Example initialValue="41.25" step="0.25" buttonSteps={4} />)

    fireEvent.click(screen.getByRole('button', { name: 'Increase Amount' }))

    expect(screen.getByRole('spinbutton', { name: 'Amount' })).toHaveValue(42.25)
  })
})
