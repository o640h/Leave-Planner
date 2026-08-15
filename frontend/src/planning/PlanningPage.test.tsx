import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PlanningPage } from './PlanningPage'
import { BookingDrawer } from './BookingDrawer'

const mocks = vi.hoisted(() => ({
  getPlanning: vi.fn(),
  getHolidaySettings: vi.fn(),
  listConsultants: vi.fn(),
  listLeaveYears: vi.fn(),
  previewBooking: vi.fn(),
  removeBooking: vi.fn(),
  saveBooking: vi.fn(),
}))

const today = new Date()
const currentIsoMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
const currentMonthLabel = today.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
const currentMonthEnd = `${currentIsoMonth}-${new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate()}`
const nextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 3)
const nextMonthHoliday = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, '0')}-03`

vi.mock('../consultants/api', () => ({ listConsultants: mocks.listConsultants }))
vi.mock('../leaveYears/api', () => ({ listLeaveYears: mocks.listLeaveYears }))
vi.mock('../publicHolidays/api', () => ({ getHolidaySettings: mocks.getHolidaySettings }))
vi.mock('./api', () => ({
  getPlanning: mocks.getPlanning,
  previewBooking: mocks.previewBooking,
  removeBooking: mocks.removeBooking,
  saveBooking: mocks.saveBooking,
}))

const zero = { dcc_hours: '0', spa_hours: '0', other_hours: '0', total_hours: '0' }
const balance = {
  opening: { dcc_hours: '203.304', spa_hours: '88.064', other_hours: '0', total_hours: '291.368' },
  carry_forward: zero,
  public_holidays: zero,
  bookings: zero,
  remaining: {
    dcc_hours: '203.304',
    spa_hours: '88.064',
    other_hours: '0',
    total_hours: '291.368',
  },
}
const workspace = {
  leave_year_id: 3,
  start_date: `${currentIsoMonth}-01`,
  end_date: currentMonthEnd,
  holidays: [],
  bookings: [],
  projected: balance,
  confirmed: balance,
  actual: balance,
  warnings: [],
}

describe('PlanningPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listConsultants.mockResolvedValue([
      { id: 7, name: 'Dr Alex Morgan', post_title: 'Consultant', archived_at: null },
      { id: 8, name: 'Dr Sam Taylor', post_title: 'Consultant', archived_at: null },
    ])
    mocks.listLeaveYears.mockImplementation((consultantId: number) =>
      Promise.resolve([
        {
          id: consultantId === 7 ? 3 : 4,
          consultant_id: consultantId,
          start_date: `${currentIsoMonth}-01`,
          end_date: currentMonthEnd,
          employment_start: null,
          employment_end: null,
        },
      ]),
    )
    mocks.getPlanning.mockResolvedValue(workspace)
    mocks.getHolidaySettings.mockResolvedValue({
      source: 'gov_uk',
      source_date: '2026-08-11',
      holidays: [{ holiday_date: nextMonthHoliday, name: 'Early May bank holiday', notes: '' }],
      corrections: [],
    })
    mocks.saveBooking.mockResolvedValue(workspace)
  })

  it('shows shared public holidays outside a consultant leave year', async () => {
    render(<PlanningPage />)

    expect(await screen.findByRole('heading', { name: currentMonthLabel })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next Month' }))
    await waitFor(() => expect(screen.queryByText('Updating…')).not.toBeInTheDocument())

    expect(await screen.findAllByTitle('Early May Bank Holiday')).toHaveLength(2)
    expect(screen.getAllByText('---')).toHaveLength(2)
  })

  it('loads every consultant into the monthly wallchart', async () => {
    render(<PlanningPage />)

    expect(await screen.findByRole('heading', { name: currentMonthLabel })).toBeInTheDocument()
    expect(await screen.findByText('Dr Alex Morgan')).toBeInTheDocument()
    expect(screen.getByText('Dr Sam Taylor')).toBeInTheDocument()
    expect(screen.getAllByText('291h')).toHaveLength(2)

    fireEvent.click(screen.getByRole('gridcell', { name: `Dr Alex Morgan, ${currentIsoMonth}-01` }))
    const drawer = screen.getByRole('dialog', { name: 'Book Leave' })
    expect(within(drawer).getByText('Dr Alex Morgan')).toBeInTheDocument()
  })

  it('previews generated daily deductions in the booking drawer', async () => {
    mocks.previewBooking.mockResolvedValue({
      days: [
        {
          leave_date: '2025-10-20',
          job_plan_id: 2,
          standard: { dcc_hours: '8', spa_hours: '0.5', other_hours: '0', total_hours: '8.5' },
          deduction: { dcc_hours: '8', spa_hours: '0.5', other_hours: '0', total_hours: '8.5' },
          override_reason: null,
          public_holiday_name: null,
        },
      ],
      projected: {
        ...balance,
        bookings: { ...zero, dcc_hours: '8', spa_hours: '0.5', total_hours: '8.5' },
      },
      confirmed: balance,
      actual: balance,
      warnings: [],
    })

    render(
      <BookingDrawer
        consultantName="Dr Alex Morgan"
        booking={null}
        initialDate={null}
        busy={false}
        onPreview={mocks.previewBooking}
        onSave={vi.fn()}
        onRemoveBooking={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    fireEvent.change(document.querySelector('#booking-start') as HTMLInputElement, {
      target: { value: '2025-10-20' },
    })
    fireEvent.change(document.querySelector('#booking-end') as HTMLInputElement, {
      target: { value: '2025-10-20' },
    })
    expect(await screen.findByRole('heading', { name: 'Daily Deductions' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('8')).toBeInTheDocument()
    await waitFor(() => expect(mocks.previewBooking).toHaveBeenCalledTimes(1))
  })

  it('loads a saved daily replacement immediately and allows an optional reason', async () => {
    const day = {
      leave_date: '2025-12-31',
      job_plan_id: 2,
      standard: { dcc_hours: '4.500', spa_hours: '1.500', other_hours: '0', total_hours: '6' },
      deduction: { dcc_hours: '4.000', spa_hours: '0.000', other_hours: '0', total_hours: '4' },
      override_reason: null,
      public_holiday_name: null,
    }
    const booking = {
      id: 12,
      leave_year_id: 3,
      start_date: day.leave_date,
      end_date: day.leave_date,
      state: 'taken' as const,
      note: null,
      days: [day],
      created_at: '2026-08-11T12:00:00',
      updated_at: '2026-08-11T12:00:00',
    }
    mocks.previewBooking.mockResolvedValue({
      days: [day],
      projected: balance,
      confirmed: balance,
      actual: balance,
      warnings: [
        {
          code: 'leave-balance.carry-forward',
          message: 'Carry-forward is included in this leave year.',
          severity: 'info',
        },
      ],
    })
    const onSave = vi.fn().mockResolvedValue(undefined)

    render(
      <BookingDrawer
        consultantName="Dr Alex Morgan"
        booking={booking}
        initialDate={null}
        busy={false}
        onPreview={mocks.previewBooking}
        onSave={onSave}
        onRemoveBooking={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(await screen.findByDisplayValue('4')).toBeInTheDocument()
    expect(screen.getByDisplayValue('0')).toBeInTheDocument()
    expect(screen.queryByText(/carry-forward is included/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /preview/i })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          overrides: [expect.objectContaining({ dcc_hours: '4', spa_hours: '0', reason: null })],
        }),
        12,
      ),
    )
  })

  it('requires confirmation before permanently removing a booking', async () => {
    const booking = {
      id: 12,
      leave_year_id: 3,
      start_date: '2025-12-31',
      end_date: '2025-12-31',
      state: 'taken' as const,
      note: null,
      days: [],
      created_at: '2026-08-11T12:00:00',
      updated_at: '2026-08-11T12:00:00',
    }
    mocks.previewBooking.mockResolvedValue({
      days: [],
      projected: balance,
      confirmed: balance,
      actual: balance,
      warnings: [],
    })
    const onRemove = vi.fn().mockResolvedValue(undefined)

    render(
      <BookingDrawer
        consultantName="Dr Alex Morgan"
        booking={booking}
        initialDate={null}
        busy={false}
        onPreview={mocks.previewBooking}
        onSave={vi.fn()}
        onRemoveBooking={onRemove}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Remove Booking' }))
    expect(onRemove).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Removal' }))
    await waitFor(() => expect(onRemove).toHaveBeenCalledWith(12))
  })
})
