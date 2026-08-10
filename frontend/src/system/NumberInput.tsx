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

    if (direction === 'up') {
      input.stepUp(buttonSteps)
    } else {
      input.stepDown(buttonSteps)
    }
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
