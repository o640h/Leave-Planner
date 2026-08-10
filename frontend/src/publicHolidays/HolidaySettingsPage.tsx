import { useEffect, useState } from 'react'
import type { SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { DateInput } from '../system/DateInput'
import {
  addHolidayCorrection,
  deleteHolidayCorrection,
  getHolidaySettings,
  syncHolidaySettings,
} from './api'
import type { HolidayCorrectionAction, HolidaySettings } from './types'
import './publicHolidays.css'

function holidayYears(settings: HolidaySettings): Array<[string, number]> {
  const counts = new Map<string, number>()
  for (const holiday of settings.holidays) {
    const year = holiday.holiday_date.slice(0, 4)
    counts.set(year, (counts.get(year) ?? 0) + 1)
  }
  return [...counts.entries()]
}

export function HolidaySettingsPage() {
  const [settings, setSettings] = useState<HolidaySettings | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [holidayDate, setHolidayDate] = useState('')
  const [action, setAction] = useState<HolidayCorrectionAction>('add_or_replace')
  const [name, setName] = useState('')
  const [reason, setReason] = useState('')

  useEffect(() => {
    getHolidaySettings()
      .then(setSettings)
      .catch((e: unknown) => setError(operatorErrorMessage(e)))
  }, [])

  async function sync() {
    setBusy(true)
    setError(null)
    try {
      setSettings(await syncHolidaySettings())
    } catch (e) {
      setError(operatorErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setSettings(
        await addHolidayCorrection({
          holiday_date: holidayDate,
          action,
          replacement_name: action === 'remove' ? null : name,
          reason,
        }),
      )
      setOpen(false)
      setHolidayDate('')
      setName('')
      setReason('')
    } catch (e) {
      setError(operatorErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  async function removeCorrection(id: number) {
    setBusy(true)
    setError(null)
    try {
      setSettings(await deleteHolidayCorrection(id))
    } catch (e) {
      setError(operatorErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="settings-page">
      <header className="settings-heading">
        <div>
          <span className="section-label">Shared Calendar</span>
          <h2>Public Holidays</h2>
        </div>
        <button
          className="button button--quiet"
          type="button"
          disabled={busy}
          onClick={() => void sync()}
        >
          {busy ? 'Updating…' : 'Sync GOV.UK'}
        </button>
      </header>
      {error ? <p className="form-notice form-notice--error">{error}</p> : null}
      {settings ? (
        <>
          <section className="settings-panel">
            <header>
              <div>
                <h3>England &amp; Wales Calendar</h3>
                <p>
                  {settings.source.replaceAll('_', ' ')} · {settings.source_date}
                </p>
              </div>
              <button
                className="button button--quiet button--with-icon"
                type="button"
                onClick={() => setOpen(true)}
              >
                <AppIcon name="plus" />
                Add Correction
              </button>
            </header>
            <div className="holiday-year-groups">
              {holidayYears(settings).map(([year, count]) => (
                <div key={year}>
                  <strong>{year}</strong>
                  <span>
                    {count} {count === 1 ? 'date' : 'dates'}
                  </span>
                </div>
              ))}
            </div>
          </section>
          <section className="settings-panel">
            <header>
              <div>
                <h3>Trust Corrections</h3>
                <p>Saved separately from the dated source calendar.</p>
              </div>
            </header>
            {settings.corrections.length ? (
              <ul className="correction-list">
                {settings.corrections.map((item) => (
                  <li key={item.id}>
                    <div>
                      <strong>
                        {item.holiday_date} ·{' '}
                        {item.action === 'remove' ? 'Removed' : item.replacement_name}
                      </strong>
                      <span>{item.reason}</span>
                    </div>
                    <button
                      className="text-button"
                      type="button"
                      disabled={busy}
                      onClick={() => void removeCorrection(item.id)}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="settings-empty">No Trust corrections are active.</p>
            )}
          </section>
        </>
      ) : (
        <p className="settings-empty">Loading the saved calendar…</p>
      )}
      {open ? (
        <div className="modal-backdrop">
          <section
            className="record-modal adjustment-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="holiday-correction-title"
          >
            <button
              className="modal-close"
              type="button"
              aria-label="Close Holiday Correction"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
            <form noValidate onSubmit={(event) => void submit(event)}>
              <header>
                <span className="section-label">Trust Calendar</span>
                <h2 id="holiday-correction-title">Add Holiday Correction</h2>
              </header>
              <div className="field">
                <label htmlFor="correction-date">Date</label>
                <DateInput
                  id="correction-date"
                  label="Date"
                  value={holidayDate}
                  onChange={setHolidayDate}
                />
              </div>
              <div className="field">
                <label htmlFor="correction-action">Action</label>
                <select
                  id="correction-action"
                  value={action}
                  onChange={(event) => setAction(event.target.value as HolidayCorrectionAction)}
                >
                  <option value="add_or_replace">Add or Replace</option>
                  <option value="remove">Remove</option>
                </select>
              </div>
              {action === 'add_or_replace' ? (
                <div className="field">
                  <label htmlFor="correction-name">Holiday Name</label>
                  <input
                    id="correction-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                </div>
              ) : null}
              <div className="field">
                <label htmlFor="correction-reason">Reason</label>
                <textarea
                  id="correction-reason"
                  rows={3}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
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
                  Save Correction
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  )
}
