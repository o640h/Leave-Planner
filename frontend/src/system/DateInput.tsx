import { useRef } from 'react'

import { AppIcon } from './AppIcon'

type Props = {
  id: string
  label: string
  value: string
  disabled?: boolean
  required?: boolean
  onChange: (value: string) => void
}

export function DateInput({ id, label, value, disabled, required, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  function openPicker() {
    const input = inputRef.current
    if (!input) return
    input.focus()
    input.showPicker?.()
  }

  return (
    <div className="date-input">
      <input
        ref={inputRef}
        id={id}
        className={!value ? 'date-input-native--empty' : undefined}
        type="date"
        value={value}
        disabled={disabled}
        aria-required={required}
        onChange={(event) => onChange(event.target.value)}
      />
      {!value && (
        <span className="date-input-placeholder" aria-hidden="true">
          --/--/----
        </span>
      )}
      <button type="button" aria-label={`Choose ${label}`} disabled={disabled} onClick={openPicker}>
        <AppIcon name="calendar" />
      </button>
    </div>
  )
}
