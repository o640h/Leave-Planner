import { useEffect, useState } from 'react'
import type { SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { formatDecimal } from '../system/decimal'
import { NumberInput } from '../system/NumberInput'
import { getCarryForward, setCarryForward } from './api'
import type { CarryForward } from './types'
import './carryForward.css'

type Props = { consultantId: number; leaveYearId: number; onSaved?: () => void }

export function CarryForwardControl({ consultantId, leaveYearId, onSaved }: Props) {
  const [record, setRecord] = useState<CarryForward | null>(null)
  const [hours, setHours] = useState('0')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasCarryForward = record !== null && formatDecimal(record.hours) !== '0'

  useEffect(() => {
    getCarryForward(consultantId, leaveYearId)
      .then((result) => {
        setRecord(result)
        setHours(formatDecimal(result.hours, 2))
      })
      .catch((requestError: unknown) => setError(operatorErrorMessage(requestError)))
  }, [consultantId, leaveYearId])

  async function save(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const saved = await setCarryForward(consultantId, leaveYearId, hours)
      setRecord(saved)
      setHours(formatDecimal(saved.hours, 2))
      setOpen(false)
      onSaved?.()
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="carry-forward-control">
      <div className="carry-forward-value">
        <span>Carry Forward</span>
        <strong>
          {record ? formatDecimal(record.hours, 2) : '—'}
          {record ? <small>hours</small> : null}
        </strong>
      </div>
      <button
        className="button button--quiet button--with-icon"
        type="button"
        onClick={() => setOpen(true)}
      >
        <AppIcon name={hasCarryForward ? 'edit' : 'plus'} />
        <span>{hasCarryForward ? 'Edit' : 'Add'}</span>
      </button>

      {error ? <p className="form-notice form-notice--error">{error}</p> : null}

      {open ? (
        <div className="modal-backdrop">
          <section
            className="record-modal carry-forward-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="carry-forward-title"
          >
            <button
              className="modal-close"
              type="button"
              aria-label="Close Carry Forward Editor"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
            <form noValidate onSubmit={(event) => void save(event)}>
              <header>
                <h2 id="carry-forward-title">Carry Forward</h2>
              </header>
              <div className="field">
                <label htmlFor="carry-forward-hours">Total Hours</label>
                <NumberInput
                  id="carry-forward-hours"
                  label="Total Hours"
                  min="0"
                  step="0.25"
                  buttonSteps={4}
                  value={hours}
                  disabled={busy}
                  onChange={setHours}
                />
                <small>Enter zero to clear the value.</small>
              </div>
              <div className="form-actions">
                <button
                  className="button button--quiet"
                  type="button"
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </button>
                <button className="button button--primary" type="submit" disabled={busy}>
                  {busy ? 'Saving…' : 'Save'}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  )
}
