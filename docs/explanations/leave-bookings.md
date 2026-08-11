# Leave Bookings and Balances

## What this part replaces

The workbook records each leave date on the Annual Leave Log and copies the DCC and SPA hours normally worked on that weekday. The application follows the same rule, but it can generate the dated rows from a start and end date and keep all consultants and years in one database.

## What the operator enters

For a booking, the operator selects:

- the consultant and leave year;
- a start and end date;
- Planned, Approved, Taken, or Cancelled;
- an optional note.

The preview finds the job plan effective on every date and shows the normal DCC and SPA deduction for that weekday. Flexible weekly hours are not assigned to a date, so they are not deducted automatically.

The operator may replace a generated daily value, for example when only DCC activity was cancelled. A replacement reason is required so the saved record still explains why it differs from the normal job plan.

## Public holidays

Public-holiday entitlement and public-holiday deductions are calculated by the holiday rules. A normal leave range that crosses a public holiday therefore records zero booking hours for that date. This prevents the same date being deducted once as a holiday and again as annual leave.

## What is saved

SQLite stores one booking record for its date range, lifecycle state, and note. It also stores a daily snapshot containing the effective job plan, normal hours, applied deduction, and any replacement reason.

Saving the daily snapshot is deliberate. If a job plan is edited later, the application can still explain what the booking deducted when it was entered. Editing and saving the booking creates a fresh preview from the current configuration before replacing those daily snapshots.

## Balance views

Balances are calculated from the applied entitlement, carry-forward, holiday deductions, and saved booking days. No mutable balance total is stored.

- **Projected** includes Planned, Approved, and Taken bookings.
- **Confirmed** includes Approved and Taken bookings.
- **Actual** includes Taken bookings only.
- **Cancelled** bookings remain visible for history but deduct nothing.

For each view:

`remaining = applied entitlement + carry-forward - holiday deductions - included booking deductions`

DCC and SPA remain separate throughout the calculation. The interface also shows their combined total.

## Warnings

The preview warns about overlaps and balances that would fall below zero. These are explanations for the operator, not silent blockers. Structurally invalid data, such as dates outside the leave year or a replacement without a reason, is rejected.

## Main code references

- `backend/src/leave_bookings/service.py` orchestrates previewing, saving, lifecycle changes, balance calculation, and audit events.
- `backend/src/leave_bookings/persistence.py` defines the SQLite booking and daily-snapshot tables.
- `backend/src/leave_records/calculator.py` contains the pure lifecycle balance calculation used by the service.
- `frontend/src/planning/PlanningPage.tsx` loads the selected planning workspace and refreshes it after changes.
- `frontend/src/planning/BookingDrawer.tsx` provides the booking preview and per-day replacement workflow.
- `frontend/src/planning/PlanningCalendar.tsx` renders holidays and bookings by date.
