import { describe, expect, it } from 'vitest'

import { addNonNegativeDecimals, formatDecimal } from './decimal'

describe('decimal display helpers', () => {
  it('hides unused decimal places without discarding meaningful precision', () => {
    expect(formatDecimal('4.000')).toBe('4')
    expect(formatDecimal('8.470')).toBe('8.47')
    expect(formatDecimal('8.475')).toBe('8.475')
  })

  it('adds PA inputs exactly without binary floating-point arithmetic', () => {
    expect(addNonNegativeDecimals('5.91', '2.56')).toBe('8.47')
    expect(addNonNegativeDecimals('0.1', '0.2')).toBe('0.3')
  })
})
