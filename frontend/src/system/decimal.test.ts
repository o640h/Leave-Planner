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

it('rounds display-only quantities without using binary floating point', () => {
  expect(formatDecimal('225.223101369863013698630137', 3)).toBe('225.223')
  expect(formatDecimal('18.71289863013698630136986301', 3)).toBe('18.713')
  expect(formatDecimal('9.9999', 3)).toBe('10')
})
