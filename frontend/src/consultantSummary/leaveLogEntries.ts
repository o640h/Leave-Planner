import type { ActivityHours, LeaveBooking } from '../planning/types'
import { addNonNegativeDecimals } from '../system/decimal'
import type { ConsultantYearSummary } from './types'

export type LeaveLogEntry = {
  key: string
  date: string
  endDate: string
  label: string
  state: string
  amounts: ActivityHours
}

function totalBookingHours(booking: LeaveBooking): ActivityHours {
  return booking.days.reduce<ActivityHours>(
    (total, day) => ({
      dcc_hours: addNonNegativeDecimals(total.dcc_hours, day.calculated_deduction.dcc_hours),
      spa_hours: addNonNegativeDecimals(total.spa_hours, day.calculated_deduction.spa_hours),
      other_hours: addNonNegativeDecimals(total.other_hours, day.calculated_deduction.other_hours),
      total_hours: addNonNegativeDecimals(total.total_hours, day.calculated_deduction.total_hours),
    }),
    { dcc_hours: '0', spa_hours: '0', other_hours: '0', total_hours: '0' },
  )
}

export function leaveLogEntries(summary: ConsultantYearSummary): LeaveLogEntry[] {
  return [
    ...summary.planning.bookings.map((booking) => ({
      key: `booking-${booking.id}`,
      date: booking.start_date,
      endDate: booking.end_date,
      label: booking.note || 'Annual Leave',
      state: booking.state,
      amounts: totalBookingHours(booking),
    })),
    ...summary.planning.holidays.map((holiday) => ({
      key: `holiday-${holiday.holiday_date}`,
      date: holiday.holiday_date,
      endDate: holiday.holiday_date,
      label: holiday.name,
      state: 'public_holiday',
      amounts: {
        dcc_hours: holiday.dcc_deduction_hours,
        spa_hours: holiday.spa_deduction_hours,
        other_hours: '0',
        total_hours: addNonNegativeDecimals(
          holiday.dcc_deduction_hours,
          holiday.spa_deduction_hours,
        ),
      },
    })),
  ].sort((left, right) => left.date.localeCompare(right.date))
}
