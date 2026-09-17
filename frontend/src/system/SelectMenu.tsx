import { useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

export type SelectMenuOption = {
  value: string
  label: string
  detail?: string
}

type SelectMenuProps = {
  id?: string
  value: string
  options: SelectMenuOption[]
  placeholder?: string
  disabled?: boolean
  ariaLabel?: string
  className?: string
  onChange: (value: string) => void
}

export function SelectMenu({
  id,
  value,
  options,
  placeholder = 'Choose an option',
  disabled = false,
  ariaLabel,
  className,
  onChange,
}: SelectMenuProps) {
  const generatedId = useId()
  const controlId = id ?? `select-menu-${generatedId}`
  const listId = `${controlId}-options`
  const triggerRef = useRef<HTMLButtonElement>(null)
  const selectedIndex = options.findIndex((option) => option.value === value)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(Math.max(selectedIndex, 0))
  const selected = selectedIndex >= 0 ? options[selectedIndex] : null

  function openMenu() {
    if (disabled) return
    setActiveIndex(Math.max(selectedIndex, 0))
    setOpen(true)
  }

  function closeMenu(restoreFocus = false) {
    setOpen(false)
    if (restoreFocus) triggerRef.current?.focus()
  }

  function choose(index: number) {
    const option = options[index]
    if (!option) return
    onChange(option.value)
    closeMenu(true)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled) return
    if (!open && ['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
      event.preventDefault()
      openMenu()
      return
    }
    if (!open) return

    if (event.key === 'Escape') {
      event.preventDefault()
      closeMenu(true)
    } else if (event.key === 'Tab') {
      closeMenu()
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((current) => Math.min(current + 1, options.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((current) => Math.max(current - 1, 0))
    } else if (event.key === 'Home') {
      event.preventDefault()
      setActiveIndex(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      setActiveIndex(Math.max(options.length - 1, 0))
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      choose(activeIndex)
    }
  }

  return (
    <div
      className={`select-menu${open ? ' select-menu--open' : ''}${
        className ? ` ${className}` : ''
      }`}
      onKeyDown={handleKeyDown}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) closeMenu()
      }}
    >
      <button
        className="select-menu-trigger"
        id={controlId}
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-label={ariaLabel}
        aria-controls={listId}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-activedescendant={open ? `${controlId}-option-${activeIndex}` : undefined}
        disabled={disabled}
        onClick={() => (open ? closeMenu() : openMenu())}
      >
        <span className={selected ? 'select-menu-value' : 'select-menu-placeholder'}>
          <span>{selected?.label ?? placeholder}</span>
          {selected?.detail ? <small>{selected.detail}</small> : null}
        </span>
        <span className="select-menu-chevron" aria-hidden="true" />
      </button>

      {open ? (
        <div className="select-menu-options" id={listId} role="listbox">
          {options.map((option, index) => (
            <button
              className={`select-menu-option${index === activeIndex ? ' is-active' : ''}${
                option.value === value ? ' is-selected' : ''
              }`}
              id={`${controlId}-option-${index}`}
              key={option.value}
              type="button"
              role="option"
              aria-selected={option.value === value}
              tabIndex={-1}
              onMouseEnter={() => setActiveIndex(index)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(index)}
            >
              <span>{option.label}</span>
              {option.detail ? <small>{option.detail}</small> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
