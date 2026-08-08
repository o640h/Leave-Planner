export function formatDecimal(value: string): string {
  if (/^-?0(?:\.0*)?$/.test(value)) return '0'

  const [whole, fraction] = value.split('.')
  const significantFraction = fraction?.replace(/0+$/, '')

  return significantFraction ? `${whole}.${significantFraction}` : whole
}

export function addNonNegativeDecimals(left: string, right: string): string {
  if (![left, right].every((value) => /^\d+(?:\.\d*)?$/.test(value))) return ''

  const decimalPlaces = Math.max(left.split('.')[1]?.length ?? 0, right.split('.')[1]?.length ?? 0)
  const toUnits = (value: string) => {
    const [whole, fraction = ''] = value.split('.')
    return BigInt(`${whole}${fraction.padEnd(decimalPlaces, '0')}`)
  }

  const digits = (toUnits(left) + toUnits(right)).toString().padStart(decimalPlaces + 1, '0')
  if (decimalPlaces === 0) return digits

  return formatDecimal(`${digits.slice(0, -decimalPlaces)}.${digits.slice(-decimalPlaces)}`)
}
