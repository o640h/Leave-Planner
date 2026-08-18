import { useRef } from 'react'

type NumberInputProps = {
  id?: string
  label: string
  value: string | number
  min?: string
  step?: string
  buttonSteps?: number
  disabled?: boolean
  inputMode?: 'decimal' | 'numeric'
  onChange: (value: string) => void
}

function decimalPlaces(value: string): number {
  return value.split('.')[1]?.length ?? 0
}

function decimalUnits(value: string, places: number): bigint | null {
  const match = /^(?<sign>-?)(?<whole>\d+)(?:\.(?<fraction>\d+))?$/.exec(value)
  if (!match?.groups) return null

  return BigInt(
    `${match.groups.sign}${match.groups.whole}${(match.groups.fraction ?? '').padEnd(places, '0')}`,
  )
}

function decimalValue(units: bigint, places: number): string {
  if (places === 0) return units.toString()

  const sign = units < 0 ? '-' : ''
  const digits = (units < 0 ? -units : units).toString().padStart(places + 1, '0')
  const fraction = digits.slice(-places).replace(/0+$/, '')
  const value = fraction ? `${digits.slice(0, -places)}.${fraction}` : digits.slice(0, -places)
  return `${sign}${value}`
}

export function NumberInput({
  id,
  label,
  value,
  min,
  step,
  buttonSteps = 1,
  disabled,
  inputMode,
  onChange,
}: NumberInputProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  function move(direction: 'up' | 'down') {
    const input = inputRef.current
    if (!input) return

    const increment = step ?? '1'
    const places = Math.max(
      decimalPlaces(input.value),
      decimalPlaces(increment),
      decimalPlaces(min ?? ''),
    )
    const currentUnits = decimalUnits(input.value, places)
    const stepUnits = decimalUnits(increment, places)
    const minimumUnits = min === undefined ? null : decimalUnits(min, places)

    if (currentUnits !== null && stepUnits !== null) {
      const movement = stepUnits * BigInt(buttonSteps)
      let nextUnits = direction === 'up' ? currentUnits + movement : currentUnits - movement
      if (minimumUnits !== null && nextUnits < minimumUnits) nextUnits = minimumUnits
      onChange(decimalValue(nextUnits, places))
      return
    }

    if (direction === 'up') input.stepUp(buttonSteps)
    else input.stepDown(buttonSteps)
    onChange(input.value)
  }

  return (
    <div className="number-input">
      <input
        ref={inputRef}
        id={id}
        type="number"
        min={min}
        step={step}
        inputMode={inputMode}
        aria-label={label}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />

      <div className="number-input-controls" aria-hidden={disabled}>
        <button
          type="button"
          aria-label={`Increase ${label}`}
          disabled={disabled}
          onClick={() => move('up')}
        >
          <svg aria-hidden="true" viewBox="0 0 12 8">
            <path d="m2 6 4-4 4 4" />
          </svg>
        </button>
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          disabled={disabled}
          onClick={() => move('down')}
        >
          <svg aria-hidden="true" viewBox="0 0 12 8">
            <path d="m2 2 4 4 4-4" />
          </svg>
        </button>
      </div>
    </div>
  )
}
