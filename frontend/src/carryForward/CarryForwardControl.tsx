import { useEffect, useState } from 'react'
import type { SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { formatDecimal } from '../system/decimal'
import { ModalLayer } from '../system/ModalLayer'
import { NumberInput } from '../system/NumberInput'
import { getCarryForward, setCarryForward } from './api'
import type { CarryForward } from './types'
import './carryForward.css'

type Props = { consultantId: number; leaveYearId: number; onSaved?: () => void }

export function CarryForwardControl({ consultantId, leaveYearId, onSaved }: Props) {
  const [record, setRecord] = useState<CarryForward | null>(null)
  const [dccHours, setDccHours] = useState('0')
  const [spaHours, setSpaHours] = useState('0')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasCarryForward = record !== null && formatDecimal(record.total_hours) !== '0'

  useEffect(() => {
    getCarryForward(consultantId, leaveYearId)
      .then((result) => {
        setRecord(result)
        setDccHours(formatDecimal(result.dcc_hours, 2))
        setSpaHours(formatDecimal(result.spa_hours, 2))
      })
      .catch((requestError: unknown) => setError(operatorErrorMessage(requestError)))
  }, [consultantId, leaveYearId])

  async function save(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const saved = await setCarryForward(consultantId, leaveYearId, dccHours, spaHours)
      setRecord(saved)
      setDccHours(formatDecimal(saved.dcc_hours, 2))
      setSpaHours(formatDecimal(saved.spa_hours, 2))
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
        <div className="carry-forward-activities">
          <strong>
            <small>DCC</small>
            {record ? formatDecimal(record.dcc_hours, 2) : '-'}
            {record ? <small>hours</small> : null}
          </strong>
          <strong>
            <small>SPA</small>
            {record ? formatDecimal(record.spa_hours, 2) : '-'}
            {record ? <small>hours</small> : null}
          </strong>
        </div>
      </div>
      <button
        className="button button--overview-action button--with-icon"
        type="button"
        onClick={() => setOpen(true)}
      >
        <AppIcon name={hasCarryForward ? 'edit' : 'plus'} />
        <span>{hasCarryForward ? 'Edit' : 'Add'}</span>
      </button>

      {error ? <p className="form-notice form-notice--error">{error}</p> : null}

      {open ? (
        <ModalLayer onClose={() => setOpen(false)}>
          <div className="modal-backdrop">
            <section
              className="record-modal record-modal--lined carry-forward-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="carry-forward-title"
              tabIndex={-1}
            >
              <button
                className="modal-close"
                type="button"
                aria-label="Close Carry Forward Editor"
                onClick={() => setOpen(false)}
              >
                x
              </button>
              <form noValidate onSubmit={(event) => void save(event)}>
                <header>
                  <h2 id="carry-forward-title">Carry Forward</h2>
                </header>
                <div className="carry-forward-fields">
                  <div className="field">
                    <label htmlFor="carry-forward-dcc-hours">DCC Hours</label>
                    <NumberInput
                      id="carry-forward-dcc-hours"
                      label="DCC Hours"
                      min="0"
                      step="0.25"
                      buttonSteps={4}
                      value={dccHours}
                      disabled={busy}
                      onChange={setDccHours}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="carry-forward-spa-hours">SPA Hours</label>
                    <NumberInput
                      id="carry-forward-spa-hours"
                      label="SPA Hours"
                      min="0"
                      step="0.25"
                      buttonSteps={4}
                      value={spaHours}
                      disabled={busy}
                      onChange={setSpaHours}
                    />
                  </div>
                </div>
                <small>Enter zero in both fields to clear the carry-forward.</small>
                <div className="form-actions">
                  <button
                    className="button button--quiet"
                    type="button"
                    onClick={() => setOpen(false)}
                  >
                    Cancel
                  </button>
                  <button className="button button--primary" type="submit" disabled={busy}>
                    {busy ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </form>
            </section>
          </div>
        </ModalLayer>
      ) : null}
    </div>
  )
}
