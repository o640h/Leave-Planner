import { useState } from 'react'

import { ApiClientError, operatorErrorMessage } from '../api/client'
import { savePdf } from '../desktop/api'
import { formatDecimal } from '../system/decimal'
import { ModalLayer } from '../system/ModalLayer'
import { getLeaveLogPdf } from './api'
import type { ConsultantYearSummary, LeaveLogEntry } from './types'

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

function formatDate(value: string): string {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return dateFormatter.format(new Date(year, month - 1, day))
}

function hours(value: string): string {
  return `${formatDecimal(value, 2)}h`
}

function stateLabel(state: string): string {
  return state.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function LeaveLedger({
  entries,
  expanded = false,
}: {
  entries: LeaveLogEntry[]
  expanded?: boolean
}) {
  return (
    <div
      className={`leave-ledger${expanded ? ' leave-ledger--expanded' : ''}`}
      role="table"
      aria-label={expanded ? 'Expanded Leave Log' : 'Leave Log'}
    >
      {expanded ? (
        <div className="leave-ledger-columns" role="row">
          <span role="columnheader">Date</span>
          <span role="columnheader">Entry</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Hours</span>
          <span role="columnheader">Activity Split</span>
        </div>
      ) : null}

      {entries.map((entry) => (
        <div className="leave-ledger-row" role="row" key={entry.key}>
          <div role="cell">
            <strong>{formatDate(entry.start_date)}</strong>
            {entry.end_date !== entry.start_date ? (
              <span> - {formatDate(entry.end_date)}</span>
            ) : null}
          </div>
          <span role="cell">{entry.description}</span>
          <span className={`ledger-state ledger-state--${entry.state}`} role="cell">
            {stateLabel(entry.state)}
          </span>
          <strong role="cell">{hours(entry.amounts.total_hours)}</strong>
          <small role="cell">
            DCC {formatDecimal(entry.amounts.dcc_hours, 2)} / SPA{' '}
            {formatDecimal(entry.amounts.spa_hours, 2)}
          </small>
        </div>
      ))}
    </div>
  )
}

export function LeaveLog({ summary }: { summary: ConsultantYearSummary }) {
  const [expanded, setExpanded] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportMessage, setExportMessage] = useState<string | null>(null)
  const [exportFailed, setExportFailed] = useState(false)
  const entries = summary.leave_log

  async function exportPdf() {
    setExporting(true)
    setExportMessage(null)
    setExportFailed(false)
    try {
      const file = await getLeaveLogPdf(summary.consultant.id, summary.leave_year.id)
      const fallbackName = `Leave_Log_${summary.leave_year.start_date}_to_${summary.leave_year.end_date}.pdf`
      const result = await savePdf(file.filename ?? fallbackName, file.blob)
      setExportMessage(result === 'saved' ? 'PDF saved.' : 'Export cancelled.')
    } catch (error) {
      setExportFailed(true)
      setExportMessage(
        error instanceof ApiClientError
          ? operatorErrorMessage(error)
          : error instanceof Error
            ? error.message
            : 'The PDF could not be exported.',
      )
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <section className="dashboard-panel summary-panel summary-panel--ledger">
        <header className="dashboard-panel-header">
          <h4>Leave Log</h4>
          <div className="leave-log-actions">
            <span>{entries.length} Entries</span>
            {entries.length ? (
              <button
                className="button button--quiet leave-log-expand"
                type="button"
                aria-label="Expand Leave Log"
                onClick={() => setExpanded(true)}
              >
                Expand
              </button>
            ) : null}
          </div>
        </header>

        {entries.length ? (
          <LeaveLedger entries={entries} />
        ) : (
          <p className="summary-empty">No leave has been logged.</p>
        )}
      </section>

      {expanded ? (
        <ModalLayer onClose={() => setExpanded(false)}>
          <div className="modal-backdrop leave-log-backdrop">
            <section
              className="record-modal leave-log-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="expanded-leave-log-title"
              tabIndex={-1}
            >
              <button
                className="modal-close"
                type="button"
                aria-label="Close Expanded Leave Log"
                disabled={exporting}
                onClick={() => setExpanded(false)}
              >
                x
              </button>

              <header className="leave-log-modal-header">
                <div>
                  <span className="section-label">Leave Log</span>
                  <h2 id="expanded-leave-log-title">{summary.consultant.name}</h2>
                  <p>{summary.consultant.post_title}</p>
                </div>
                <div className="leave-log-context">
                  <span>
                    {formatDate(summary.leave_year.start_date)} -{' '}
                    {formatDate(summary.leave_year.end_date)}
                  </span>
                  <div className="leave-log-export-actions">
                    <strong>{entries.length} Entries</strong>
                    <button
                      className="button button--primary leave-log-export-button"
                      type="button"
                      disabled={exporting}
                      onClick={() => void exportPdf()}
                    >
                      {exporting ? 'Preparing PDF...' : 'Export PDF'}
                    </button>
                  </div>
                </div>
              </header>

              {exportMessage ? (
                <p
                  className={`leave-log-export-status${exportFailed ? ' leave-log-export-status--error' : ''}`}
                  role={exportFailed ? 'alert' : 'status'}
                >
                  {exportMessage}
                </p>
              ) : null}

              <LeaveLedger entries={entries} expanded />
            </section>
          </div>
        </ModalLayer>
      ) : null}
    </>
  )
}
