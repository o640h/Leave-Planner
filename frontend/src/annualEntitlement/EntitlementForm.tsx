import { useState } from 'react'
import type { SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import { NumberInput } from '../system/NumberInput'
import { formatDecimal } from '../system/decimal'
import type {
  EntitlementApplyInput,
  EntitlementMode,
  EntitlementRecommendation,
  EntitlementWorkspace,
} from './types'

type EntitlementFormProps = {
  initialValue: EntitlementWorkspace
  busy: boolean
  onPreview: (sevenYearsOrMore: boolean) => Promise<EntitlementRecommendation>
  onSubmit: (details: EntitlementApplyInput) => Promise<void>
  onCancel: () => void
}

type AmountSummaryProps = {
  title: string
  amounts: EntitlementRecommendation['recommended_entitlement']
  emphasis?: boolean
}

function AmountSummary({ title, amounts, emphasis = false }: AmountSummaryProps) {
  return (
    <section
      className={`entitlement-breakdown${emphasis ? ' entitlement-breakdown--emphasis' : ''}`}
    >
      <h4>{title}</h4>
      <dl>
        <div>
          <dt>DCC</dt>
          <dd>{formatDecimal(amounts.dcc_hours, 3)}</dd>
        </div>
        <div>
          <dt>SPA</dt>
          <dd>{formatDecimal(amounts.spa_hours, 3)}</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>{formatDecimal(amounts.total_hours, 3)}</dd>
        </div>
      </dl>
    </section>
  )
}

export function EntitlementForm({
  initialValue,
  busy,
  onPreview,
  onSubmit,
  onCancel,
}: EntitlementFormProps) {
  const application = initialValue.application
  const storedRecommendation = initialValue.recommendation

  const [mode, setMode] = useState<EntitlementMode>(application?.mode ?? 'calculated')
  const [sevenYearsOrMore, setSevenYearsOrMore] = useState(
    storedRecommendation?.inputs.seven_years_or_more ?? false,
  )
  const [dccHours, setDccHours] = useState(
    application ? formatDecimal(application.entitlement.dcc_hours, 3) : '',
  )
  const [spaHours, setSpaHours] = useState(
    application ? formatDecimal(application.entitlement.spa_hours, 3) : '',
  )
  const [reason, setReason] = useState(application?.reason ?? '')
  const [preview, setPreview] = useState<EntitlementRecommendation | null>(storedRecommendation)
  const [previewing, setPreviewing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const calculatedMode = mode === 'calculated'
  const editableAmounts = mode === 'manual'
  const disabled = busy || previewing

  function changeMode(nextMode: EntitlementMode) {
    setMode(nextMode)
    setError(null)
  }

  async function requestPreview() {
    setPreviewing(true)
    setError(null)

    try {
      const result = await onPreview(sevenYearsOrMore)
      setPreview(result)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setPreviewing(false)
    }
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()

    if (calculatedMode && preview === null) {
      setError('Preview the recommendation before applying these values.')
      return
    }

    if (editableAmounts && (!dccHours || !spaHours)) {
      setError('Enter the applied DCC and SPA hours.')
      return
    }

    const details: EntitlementApplyInput = {
      mode,
      other_hours: '0',
    }

    if (calculatedMode) {
      details.seven_years_or_more = sevenYearsOrMore
    }

    if (editableAmounts) {
      details.dcc_hours = dccHours
      details.spa_hours = spaHours
      details.reason = reason.trim() || null
    }

    setError(null)
    await onSubmit(details)
  }

  return (
    <form className="entitlement-form" noValidate onSubmit={handleSubmit}>
      <div className="form-introduction">
        <span className="section-label">Annual Entitlement</span>
        <h3 id="entitlement-form-title">Configure Entitlement</h3>
        <p>Compare the calculated recommendation with the values applied to this leave year.</p>
      </div>

      {error ? (
        <p className="form-notice form-notice--error" role="alert">
          {error}
        </p>
      ) : null}

      <fieldset className="entitlement-mode-selector">
        <legend>Application Method</legend>
        <div className="entitlement-mode-options">
          <label>
            <input
              type="radio"
              name="entitlement-mode"
              value="calculated"
              checked={mode === 'calculated'}
              disabled={disabled}
              onChange={() => changeMode('calculated')}
            />
            <strong>Use Recommendation</strong>
          </label>

          <label>
            <input
              type="radio"
              name="entitlement-mode"
              value="manual"
              checked={mode === 'manual'}
              disabled={disabled}
              onChange={() => changeMode('manual')}
            />
            <strong>Enter Manually</strong>
          </label>
        </div>
      </fieldset>

      {calculatedMode ? (
        <section className="entitlement-input-section">
          <header>
            <h4>Calculation Inputs</h4>
          </header>

          <label className="entitlement-service-confirmation">
            <input
              type="checkbox"
              checked={sevenYearsOrMore}
              disabled={disabled}
              onChange={(event) => {
                setSevenYearsOrMore(event.target.checked)
                setPreview(null)
                setError(null)
              }}
            />
            <span>
              <strong>Seven Years or More</strong>
              <small>Apply the seven-year service entitlement for this leave year.</small>
            </span>
          </label>

          <button
            className="button button--quiet"
            type="button"
            disabled={disabled}
            onClick={requestPreview}
          >
            {previewing ? 'Calculating...' : 'Preview Recommendation'}
          </button>
        </section>
      ) : null}

      {preview ? (
        <div className="entitlement-preview">
          <AmountSummary title="Base Annual Leave" amounts={preview.base_entitlement} />
          <AmountSummary title="Public Holidays" amounts={preview.public_holiday_entitlement} />
          <AmountSummary
            title="Recommended Total"
            amounts={preview.recommended_entitlement}
            emphasis
          />
        </div>
      ) : null}

      {editableAmounts ? (
        <section className="entitlement-input-section">
          <header>
            <h4>Applied Values</h4>
          </header>

          <div className="entitlement-hour-fields">
            <div className="field">
              <label htmlFor="entitlement-dcc-hours">DCC Hours</label>
              <NumberInput
                id="entitlement-dcc-hours"
                label="DCC Hours"
                value={dccHours}
                min="0"
                step="0.25"
                disabled={disabled}
                inputMode="decimal"
                onChange={(value) => {
                  setDccHours(value)
                  setError(null)
                }}
              />
            </div>

            <div className="field">
              <label htmlFor="entitlement-spa-hours">SPA Hours</label>
              <NumberInput
                id="entitlement-spa-hours"
                label="SPA Hours"
                value={spaHours}
                min="0"
                step="0.25"
                disabled={disabled}
                inputMode="decimal"
                onChange={(value) => {
                  setSpaHours(value)
                  setError(null)
                }}
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="entitlement-reason">Reason (Optional)</label>
            <textarea
              id="entitlement-reason"
              rows={3}
              value={reason}
              disabled={disabled}
              onChange={(event) => {
                setReason(event.target.value)
                setError(null)
              }}
            />
          </div>
        </section>
      ) : null}

      <div className="form-actions">
        <button
          className="button button--quiet"
          type="button"
          disabled={disabled}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button className="button button--primary" type="submit" disabled={disabled}>
          {busy ? 'Applying...' : 'Apply Entitlement'}
        </button>
      </div>
    </form>
  )
}
