export type LeaveYear = {
  id: number
  consultant_id: number
  start_date: string
  end_date: string
  employment_start: string | null
  employment_end: string | null
}

export type LeaveYearInput = {
  start_date: string
  end_date: string
  employment_start: string | null
  employment_end: string | null
}

export const emptyLeaveYearInput = (): LeaveYearInput => ({
  start_date: '',
  end_date: '',
  employment_start: null,
  employment_end: null,
})
