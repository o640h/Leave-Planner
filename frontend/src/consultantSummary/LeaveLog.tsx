import { useState } from 'react'

import { formatDecimal } from '../system/decimal'
import { ModalLayer } from '../system/ModalLayer'
import { leaveLogEntries } from './leaveLogEntries'
import type { LeaveLogEntry } from './leaveLogEntries'
import type { ConsultantYearSummary } from './types'

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
            <strong>{formatDate(entry.date)}</strong>
            {entry.endDate !== entry.date ? <span> - {formatDate(entry.endDate)}</span> : null}
          </div>
          <span role="cell">{entry.label}</span>
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
  const entries = leaveLogEntries(summary)

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
                  <strong>{entries.length} Entries</strong>
                </div>
              </header>

              <LeaveLedger entries={entries} expanded />
            </section>
          </div>
        </ModalLayer>
      ) : null}
    </>
  )
}
