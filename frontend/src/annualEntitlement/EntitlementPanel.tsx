import { useEffect, useRef, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { formatDecimal } from '../system/decimal'
import { applyEntitlement, getEntitlement, previewEntitlement, refreshEntitlement } from './api'
import { EntitlementCalculationDetails } from './EntitlementCalculationDetails'
import { EntitlementForm } from './EntitlementForm'
import type {
  EntitlementApplyInput,
  EntitlementMode,
  EntitlementRecommendation,
  EntitlementWorkspace,
} from './types'
import './annualEntitlement.css'

type EntitlementPanelProps = {
  consultantId: number
  leaveYearId: number
  onStatusChange?: (configured: boolean | null) => void
  refreshRevision: number
  reloadRevision: number
}

const modeLabels: Record<EntitlementMode, string> = {
  calculated: 'Calculated',
  calculated_with_override: 'Calculated With Override',
  manual: 'Manual',
}

export function EntitlementPanel({
  consultantId,
  leaveYearId,
  onStatusChange,
  refreshRevision,
  reloadRevision,
}: EntitlementPanelProps) {
  const [workspace, setWorkspace] = useState<EntitlementWorkspace>({
    recommendation: null,
    application: null,
  })
  const [editorOpen, setEditorOpen] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const seenRefreshRevision = useRef(refreshRevision)
  const seenReloadRevision = useRef(reloadRevision)

  useEffect(() => {
    onStatusChange?.(null)

    getEntitlement(consultantId, leaveYearId)
      .then((result) => {
        setWorkspace(result)
        onStatusChange?.(result.application !== null)
      })
      .catch((requestError: unknown) => {
        setError(operatorErrorMessage(requestError))
        onStatusChange?.(null)
      })
      .finally(() => setLoading(false))
  }, [consultantId, leaveYearId, loadAttempt, onStatusChange])

  useEffect(() => {
    if (refreshRevision === seenRefreshRevision.current) return
    seenRefreshRevision.current = refreshRevision
    setRefreshError(null)

    refreshEntitlement(consultantId, leaveYearId)
      .then((result) => {
        setWorkspace(result)
        onStatusChange?.(result.application !== null)

        if (result.application?.mode === 'calculated') {
          setNotice('The annual entitlement was recalculated.')
        } else if (result.application?.mode === 'calculated_with_override') {
          setNotice('The recommendation was recalculated; the applied override was kept.')
        } else if (result.application?.mode === 'manual') {
          setNotice(
            'The manual entitlement was kept. Review it if the change affects approved hours.',
          )
        }
      })
      .catch((requestError: unknown) => {
        setRefreshError(operatorErrorMessage(requestError))
      })
  }, [consultantId, leaveYearId, onStatusChange, refreshRevision])

  useEffect(() => {
    if (reloadRevision === seenReloadRevision.current) return
    seenReloadRevision.current = reloadRevision
    setRefreshError(null)

    getEntitlement(consultantId, leaveYearId)
      .then((result) => {
        setWorkspace(result)
        onStatusChange?.(result.application !== null)
      })
      .catch((requestError: unknown) => {
        setRefreshError(operatorErrorMessage(requestError))
      })
  }, [consultantId, leaveYearId, onStatusChange, reloadRevision])

  function requestPreview(
    appointmentDate: string,
    serviceStartDate: string,
  ): Promise<EntitlementRecommendation> {
    return previewEntitlement(consultantId, leaveYearId, appointmentDate, serviceStartDate)
  }

  async function saveEntitlement(details: EntitlementApplyInput) {
    setSaving(true)
    setError(null)
    setNotice(null)

    try {
      const saved = await applyEntitlement(consultantId, leaveYearId, details)
      setWorkspace(saved)
      setEditorOpen(false)
      setNotice('The annual entitlement was applied.')
      onStatusChange?.(true)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setSaving(false)
    }
  }

  const application = workspace.application
  const recommendation = workspace.recommendation

  return (
    <section className="dashboard-panel entitlement-panel" aria-labelledby="entitlement-title">
      <header className="dashboard-panel-header">
        <div>
          <h4 id="entitlement-title">Annual Entitlement</h4>
        </div>

        <button
          className="button button--quiet button--with-icon"
          type="button"
          onClick={() => {
            setError(null)
            setEditorOpen(true)
          }}
        >
          <AppIcon name={application ? 'edit' : 'plus'} />
          <span>{application ? 'Edit' : 'Configure'}</span>
        </button>
      </header>

      {notice ? (
        <p className="form-notice form-notice--success" role="status">
          {notice}
        </p>
      ) : null}

      {refreshError ? (
        <p className="form-notice form-notice--error" role="alert">
          The previous entitlement remains applied. Recalculation needs attention: {refreshError}
        </p>
      ) : null}

      {loading ? (
        <p className="entitlement-message">Loading entitlement...</p>
      ) : error && !editorOpen ? (
        <div className="entitlement-message form-notice--error" role="alert">
          <p>{error}</p>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setLoading(true)
              setError(null)
              setLoadAttempt((attempt) => attempt + 1)
            }}
          >
            Try Again
          </button>
        </div>
      ) : application ? (
        <div className="entitlement-content">
          <div className="applied-entitlement-summary">
            <div>
              <span>Application Method</span>
              <strong>{modeLabels[application.mode]}</strong>
            </div>
            <div>
              <span>DCC</span>
              <strong>{formatDecimal(application.entitlement.dcc_hours)}</strong>
            </div>
            <div>
              <span>SPA</span>
              <strong>{formatDecimal(application.entitlement.spa_hours)}</strong>
            </div>
            <div>
              <span>Total Hours</span>
              <strong>{formatDecimal(application.entitlement.total_hours)}</strong>
            </div>
          </div>

          {recommendation ? (
            <>
              <div className="entitlement-components">
                <div>
                  <span>Base Annual Leave</span>
                  <strong>{formatDecimal(recommendation.base_entitlement.total_hours)}</strong>
                </div>
                <div>
                  <span>Public Holidays</span>
                  <strong>
                    {formatDecimal(recommendation.public_holiday_entitlement.total_hours)}
                  </strong>
                </div>
                <div>
                  <span>Recommended</span>
                  <strong>
                    {formatDecimal(recommendation.recommended_entitlement.total_hours)}
                  </strong>
                </div>
              </div>

              <EntitlementCalculationDetails recommendation={recommendation} />
            </>
          ) : (
            <p className="manual-entitlement-note">
              These values were entered manually.
              {application.reason ? ` ${application.reason}` : ''}
            </p>
          )}
        </div>
      ) : (
        <div className="entitlement-message entitlement-message--empty">
          <p>No annual entitlement has been applied.</p>
          <span>Calculate a recommendation or enter approved DCC and SPA hours manually.</span>
        </div>
      )}

      {editorOpen ? (
        <div className="modal-backdrop">
          <section
            className="record-modal entitlement-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="entitlement-form-title"
          >
            <button
              className="modal-close"
              type="button"
              aria-label="Close Entitlement Editor"
              disabled={saving}
              onClick={() => setEditorOpen(false)}
            >
              ×
            </button>

            {error ? (
              <p className="form-notice form-notice--error" role="alert">
                {error}
              </p>
            ) : null}

            <EntitlementForm
              initialValue={workspace}
              busy={saving}
              onPreview={requestPreview}
              onSubmit={saveEntitlement}
              onCancel={() => setEditorOpen(false)}
            />
          </section>
        </div>
      ) : null}
    </section>
  )
}
