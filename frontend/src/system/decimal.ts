function roundDecimal(value: string, places: number): string {
  const match = /^(?<sign>-?)(?<whole>\d+)(?:\.(?<fraction>\d+))?$/.exec(value)
  const fraction = match?.groups?.fraction ?? ''
  if (!match?.groups || fraction.length <= places) return value

  const sign = match.groups.sign
  const whole = match.groups.whole
  const kept = fraction.slice(0, places)
  const units = BigInt(`${whole}${kept}`) + (fraction[places] >= '5' ? 1n : 0n)
  const digits = units.toString().padStart(whole.length + places, '0')

  if (places === 0) return `${sign}${digits}`
  return `${sign}${digits.slice(0, -places)}.${digits.slice(-places)}`
}

export function formatDecimal(value: string, maxDecimalPlaces?: number): string {
  const rounded = maxDecimalPlaces === undefined ? value : roundDecimal(value, maxDecimalPlaces)

  if (/^-?0(?:\.0*)?$/.test(rounded)) return '0'

  const [whole, fraction] = rounded.split('.')
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
