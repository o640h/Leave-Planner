import { apiRequest } from '../api/client'
import type {
  HolidayCorrectionAction,
  HolidaySettings,
  HolidayTreatmentInput,
  LeaveYearHolidays,
} from './types'

const settingsPath = '/api/settings/public-holidays'

export const getHolidaySettings = () => apiRequest<HolidaySettings>(settingsPath)
export const syncHolidaySettings = () =>
  apiRequest<HolidaySettings>(`${settingsPath}/sync`, { method: 'POST' })
export const addHolidayCorrection = (details: {
  holiday_date: string
  action: HolidayCorrectionAction
  replacement_name: string | null
  reason: string
}) =>
  apiRequest<HolidaySettings>(`${settingsPath}/corrections`, {
    method: 'POST',
    body: JSON.stringify(details),
  })
export const deleteHolidayCorrection = (id: number) =>
  apiRequest<HolidaySettings>(`${settingsPath}/corrections/${id}`, { method: 'DELETE' })

function yearPath(consultantId: number, leaveYearId: number): string {
  return `/api/consultants/${consultantId}/leave-years/${leaveYearId}/public-holidays`
}
export const getLeaveYearHolidays = (consultantId: number, leaveYearId: number) =>
  apiRequest<LeaveYearHolidays>(yearPath(consultantId, leaveYearId))
export const saveHolidayTreatment = (
  consultantId: number,
  leaveYearId: number,
  holidayDate: string,
  details: HolidayTreatmentInput,
) =>
  apiRequest<LeaveYearHolidays>(`${yearPath(consultantId, leaveYearId)}/${holidayDate}/treatment`, {
    method: 'PUT',
    body: JSON.stringify(details),
  })
