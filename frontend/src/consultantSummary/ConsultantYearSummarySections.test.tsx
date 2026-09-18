import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ConsultantYearSummary } from './types'
import { ConsultantYearSummarySections, LeaveBalanceSummary } from './ConsultantYearSummarySections'

const hours = (dcc: string, spa: string, total: string) => ({
  dcc_hours: dcc,
  spa_hours: spa,
  other_hours: '0',
  total_hours: total,
})

const approved = {
  available: hours('244.554', '88.064', '332.618'),
  used: hours('229.5', '18', '247.5'),
  remaining: hours('15.054', '70.064', '85.118'),
}

const summary = {
  consultant: {
    id: 1,
    name: 'Anonymous',
    post_title: 'Consultant in Radiology',
    archived_at: null,
  },
  leave_year: {
    id: 2,
    consultant_id: 1,
    start_date: '2025-08-29',
    end_date: '2026-08-28',
    employment_start: null,
    employment_end: null,
  },
  job_plans: [],
  entitlement: { recommendation: null, application: null },
  carry_forward: {
    id: 3,
    leave_year_id: 2,
    dcc_hours: '41.25',
    spa_hours: '0',
    total_hours: '41.25',
    created_at: null,
  },
  allocation_source: 'recommendation',
  job_plan_periods: [
    {
      job_plan_id: 4,
      effective_from: '2025-08-29',
      effective_until: '2026-07-31',
      calendar_days: 337,
      contracted_pas: '8.47',
      dcc_pas: '5.91',
      spa_pas: '2.56',
      standard_dcc_hours: '20.5',
      standard_spa_hours: '4',
      gross_entitlement_hours: '269.0164821917808219',
      dcc_entitlement_hours: '187.7080767',
      spa_entitlement_hours: '81.3084055',
    },
  ],
  planning: {
    leave_year_id: 2,
    start_date: '2025-08-29',
    end_date: '2026-08-28',
    holidays: [],
    bookings: [
      {
        id: 5,
        leave_year_id: 2,
        start_date: '2025-10-20',
        end_date: '2025-10-20',
        state: 'approved',
        note: 'Workbook reference',
        days: [
          {
            leave_date: '2025-10-20',
            job_plan_id: 4,
            contracted_pas: null,
            deduction_factor: null,
            standard: hours('8', '0.5', '8.5'),
            deduction: hours('8', '0.5', '8.5'),
            calculated_deduction: hours('8', '0.5', '8.5'),
            override_reason: null,
            public_holiday_name: null,
          },
        ],
        created_at: '2026-08-11T10:00:00',
        updated_at: '2026-08-11T10:00:00',
      },
    ],
    requested: null,
    approved: null,
    warnings: [],
  },
  leave_log: [
    {
      key: 'booking-5',
      start_date: '2025-10-20',
      end_date: '2025-10-20',
      description: 'Workbook reference',
      state: 'approved',
      amounts: hours('8', '0.5', '8.5'),
    },
  ],
  balances: { requested: approved, approved },
  weekday_counts: { monday: 14, tuesday: 12, wednesday: 12, thursday: 2, friday: 2 },
  warnings: [],
  audit_events: [
    {
      id: 6,
      actor_label: 'Admin',
      entity_type: 'leave_booking',
      action: 'created',
      recorded_at: '2026-08-11T10:00:00',
      details: {},
    },
  ],
} satisfies ConsultantYearSummary

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('consultant year summary', () => {
  it('shows the workbook period calculation and compact leave log', () => {
    render(<ConsultantYearSummarySections summary={summary} />)

    expect(screen.getByText('337')).toBeInTheDocument()
    expect(screen.getByText('20.5 DCC / 4 SPA')).toBeInTheDocument()
    expect(screen.getByText('269h')).toBeInTheDocument()
    expect(screen.getByText('DCC 187.7 / SPA 81.3')).toBeInTheDocument()
    expect(screen.getByText('Workbook reference')).toBeInTheDocument()
    expect(screen.getByText('8.5h')).toBeInTheDocument()
    expect(screen.getByText('1 Events')).toBeInTheDocument()
    expect(screen.getByText(/Admin ·/)).toBeInTheDocument()
  })

  it('switches between approved and requested balances', () => {
    render(<LeaveBalanceSummary summary={summary} />)

    expect(screen.getByText('248h')).toBeInTheDocument()
    expect(screen.getByText('85h')).toBeInTheDocument()
    expect(screen.getByText('14')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Requested' }))
    expect(screen.getByRole('button', { name: 'Requested' })).toHaveClass('balance-tab--active')
  })

  it('opens the complete leave log in an identified workspace view', () => {
    render(<ConsultantYearSummarySections summary={summary} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Leave Log' }))

    expect(screen.getByRole('dialog', { name: 'Anonymous' })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Expanded Leave Log' })).toBeInTheDocument()
    expect(screen.getByText('29 Aug 2025 - 28 Aug 2026')).toBeInTheDocument()
    expect(screen.getAllByText('Workbook reference')).toHaveLength(2)

    fireEvent.click(screen.getByRole('button', { name: 'Close Expanded Leave Log' }))
    expect(screen.queryByRole('dialog', { name: 'Anonymous' })).not.toBeInTheDocument()
  })

  it('downloads the generated PDF through the browser', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:leave-log')
    const revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(new Blob(['%PDF-1.4\ntest']), {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition':
              'attachment; filename="Anonymous_Leave_Log_2025-08-29_to_2026-08-28.pdf"',
          },
        }),
      ),
    )
    render(<ConsultantYearSummarySections summary={summary} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Leave Log' }))
    fireEvent.click(screen.getByRole('button', { name: 'Export PDF' }))

    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce())
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:leave-log')
    expect(await screen.findByRole('status')).toHaveTextContent('PDF download started.')
  })
})
