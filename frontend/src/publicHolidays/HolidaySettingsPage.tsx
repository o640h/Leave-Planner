import { useEffect, useState } from 'react'
import type { SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { DateInput } from '../system/DateInput'
import { ModalLayer } from '../system/ModalLayer'
import {
  addHolidayCorrection,
  deleteHolidayCorrection,
  getHolidaySettings,
  syncHolidaySettings,
} from './api'
import type { Holiday, HolidayCorrectionAction, HolidaySettings } from './types'
import './publicHolidays.css'

function holidayYears(settings: HolidaySettings): Array<[string, Holiday[]]> {
  const groups = new Map<string, Holiday[]>()
  for (const holiday of settings.holidays) {
    const year = holiday.holiday_date.slice(0, 4)
    groups.set(year, [...(groups.get(year) ?? []), holiday])
  }
  return [...groups.entries()]
}

function displayDate(value: string, includeYear = false) {
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: includeYear ? 'numeric' : undefined,
  })
}

function sourceName(source: string) {
  return source === 'gov_uk_sync' ? 'GOV.UK' : 'Built-In Snapshot'
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
  const [selectedYear, setSelectedYear] = useState('')

  const groupedYears = settings ? holidayYears(settings) : []
  const currentYear = String(new Date().getFullYear())
  const activeYear = groupedYears.some(([year]) => year === selectedYear)
    ? selectedYear
    : groupedYears.some(([year]) => year === currentYear)
      ? currentYear
      : (groupedYears.at(-1)?.[0] ?? '')
  const activeHolidays = groupedYears.find(([year]) => year === activeYear)?.[1] ?? []

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
    <section className="settings-section" aria-labelledby="public-holidays-title">
      <header className="settings-content-heading settings-heading">
        <div>
          <span className="section-label">Shared Calendar</span>
          <h2 id="public-holidays-title">Public Holidays</h2>
        </div>
      </header>
      {error ? <p className="form-notice form-notice--error">{error}</p> : null}
      {settings ? (
        <>
          <section className="settings-panel holiday-calendar-panel">
            <header className="holiday-calendar-header">
              <div>
                <h3>England &amp; Wales Calendar</h3>
                <p>Official bank holidays used throughout Leave Planner.</p>
              </div>
              <div className="holiday-source">
                <span>{sourceName(settings.source)}</span>
                <strong>Updated {displayDate(settings.source_date, true)}</strong>
                <button
                  className="button button--overview-action"
                  type="button"
                  disabled={busy}
                  onClick={() => void sync()}
                >
                  {busy ? 'Updating...' : 'Sync GOV.UK'}
                </button>
              </div>
            </header>
            <div className="holiday-year-tabs" role="tablist" aria-label="Calendar Year">
              {groupedYears.map(([year, holidays]) => (
                <button
                  className={
                    year === activeYear
                      ? 'holiday-year-tab holiday-year-tab--active'
                      : 'holiday-year-tab'
                  }
                  type="button"
                  role="tab"
                  aria-selected={year === activeYear}
                  key={year}
                  onClick={() => setSelectedYear(year)}
                >
                  <strong>{year}</strong>
                  <span>
                    {holidays.length} {holidays.length === 1 ? 'Date' : 'Dates'}
                  </span>
                </button>
              ))}
            </div>
            <div
              className="holiday-year-detail"
              role="tabpanel"
              aria-label={`${activeYear} Holidays`}
            >
              <header>
                <strong>{activeYear}</strong>
                <span>
                  {activeHolidays.length}{' '}
                  {activeHolidays.length === 1 ? 'Public Holiday' : 'Public Holidays'}
                </span>
              </header>
              <ul>
                {activeHolidays.map((holiday) => (
                  <li key={holiday.holiday_date}>
                    <time dateTime={holiday.holiday_date}>{displayDate(holiday.holiday_date)}</time>
                    <strong>{holiday.name}</strong>
                  </li>
                ))}
              </ul>
            </div>
          </section>
          <section className="settings-panel corrections-panel">
            <header>
              <div>
                <h3>Corrections</h3>
                <p>
                  {settings.corrections.length
                    ? `${settings.corrections.length} Active`
                    : 'None Active'}
                </p>
              </div>
              <button
                className="button button--overview-action button--with-icon"
                type="button"
                onClick={() => setOpen(true)}
              >
                <AppIcon name="plus" />
                Add Correction
              </button>
            </header>
            {settings.corrections.length ? (
              <ul className="correction-list">
                {settings.corrections.map((item) => (
                  <li key={item.id}>
                    <div>
                      <strong>
                        {item.holiday_date} /{' '}
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
              <p className="settings-empty">No corrections have been added.</p>
            )}
          </section>
        </>
      ) : (
        <p className="settings-empty">Loading the saved calendar...</p>
      )}
      {open ? (
        <ModalLayer onClose={() => setOpen(false)}>
          <div className="modal-backdrop">
            <section
              className="record-modal record-modal--lined adjustment-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="holiday-correction-title"
              tabIndex={-1}
            >
              <button
                className="modal-close"
                type="button"
                aria-label="Close Holiday Correction"
                onClick={() => setOpen(false)}
              >
                x
              </button>
              <form noValidate onSubmit={(event) => void submit(event)}>
                <header>
                  <span className="section-label">Shared Calendar</span>
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
        </ModalLayer>
      ) : null}
    </section>
  )
}
