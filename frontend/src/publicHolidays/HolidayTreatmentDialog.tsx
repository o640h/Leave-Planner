import { useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { ModalLayer } from '../system/ModalLayer'
import type { HolidayOccurrence, HolidayTreatmentBasis, HolidayTreatmentInput } from './types'

type Props = {
  occurrence: HolidayOccurrence
  onSave: (details: HolidayTreatmentInput) => Promise<void>
  onClose: () => void
}

export function HolidayTreatmentDialog({ occurrence, onSave, onClose }: Props) {
  const [basis, setBasis] = useState<HolidayTreatmentBasis>(occurrence.basis)
  const [note, setNote] = useState(occurrence.treatment_note ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    const retainedNote = note.trim()
    setSaving(true)
    setError(null)
    try {
      await onSave({
        basis,
        note: basis === 'qualifying_on_call' ? retainedNote || null : null,
      })
      onClose()
    } catch (caught) {
      setError(operatorErrorMessage(caught))
    } finally {
      setSaving(false)
    }
  }

  const restoringStandard = occurrence.basis === 'qualifying_on_call' && basis === 'standard'

  return (
    <ModalLayer onClose={() => !saving && onClose()}>
      <div className="modal-backdrop">
        <section
          className="record-modal record-modal--lined adjustment-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="holiday-treatment-title"
          tabIndex={-1}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close Holiday Treatment"
            disabled={saving}
            onClick={onClose}
          >
            X
          </button>
          <header>
            <span className="section-label">{occurrence.holiday_date}</span>
            <h2 id="holiday-treatment-title">{occurrence.name}</h2>
          </header>
          {error ? (
            <p className="form-notice form-notice--error" id="holiday-treatment-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="field">
            <label htmlFor="holiday-basis">Treatment</label>
            <select
              id="holiday-basis"
              value={basis}
              disabled={saving}
              aria-describedby={error ? 'holiday-treatment-error' : undefined}
              onChange={(event) => {
                setBasis(event.target.value as HolidayTreatmentBasis)
                setError(null)
              }}
            >
              <option value="standard">Standard Deduction</option>
              <option value="qualifying_on_call">Qualifying On Call - Retain Leave</option>
            </select>
          </div>
          {basis === 'qualifying_on_call' ? (
            <>
              <div className="field">
                <label htmlFor="holiday-note">Reason (Optional)</label>
                <textarea
                  id="holiday-note"
                  rows={3}
                  value={note}
                  disabled={saving}
                  aria-describedby={error ? 'holiday-treatment-error' : undefined}
                  onChange={(event) => {
                    setNote(event.target.value)
                    setError(null)
                  }}
                />
              </div>
            </>
          ) : null}
          <div className="form-actions">
            <button
              className="button button--quiet"
              type="button"
              disabled={saving}
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="button button--primary"
              type="button"
              disabled={saving}
              onClick={() => void save()}
            >
              {saving
                ? 'Saving...'
                : restoringStandard
                  ? 'Restore Standard Treatment'
                  : 'Save Treatment'}
            </button>
          </div>
        </section>
      </div>
    </ModalLayer>
  )
}
