# Leave Log Export

## Operator outcome

The expanded Leave Log can create a clean A4 PDF for the selected consultant and leave year. The
document includes consultant identity, the inclusive leave-year dates, every on-screen leave-log
entry, booking state, DCC and SPA deductions, total hours, the Actual Leave Remaining balance, a
generated timestamp, page numbers, and reconciled totals. Multi-page tables repeat their column
headings.

The PDF deliberately uses a light, printer-friendly document design rather than copying the dark
application interface. It is intended to be opened, printed, screenshotted, or sent directly to the
consultant.

## One source for screen and export

`consultant_year_summary.leave_log.leave_log_entries` turns the planning result into chronological
booking and public-holiday rows. Booking rows use the persisted calculated deductions shown in the
balance ledger. Public holidays use their date-specific calculated deductions. The summary API
returns these rows to the expanded frontend view, and the PDF generator consumes the same rows.

This keeps the displayed DCC, SPA, and total values identical to the exported values. A date-range
booking remains one row with its combined deduction, matching the on-screen Leave Log.

## Browser download flow

The export endpoint creates PDF bytes in memory and never accepts or writes an operator-provided
filesystem path. The React interface retrieves those bytes, creates a short-lived browser object URL,
and starts a download using the safe filename supplied by the server. The object URL is revoked as
soon as the download starts. The browser controls whether it asks for a destination or uses its
configured downloads directory.

Leave Remaining uses the Actual balance because the leave-log totals contain Taken leave and
public-holiday deductions. If annual entitlement has not been applied, the PDF explains that the
balance is unavailable instead of inventing a value.

## Files to follow

- `backend/src/consultant_year_summary/leave_log.py` builds shared leave-log rows.
- `backend/src/consultant_year_summary/report.py` creates the multipage ReportLab PDF.
- `backend/src/consultant_year_summary/router.py` exposes the in-memory PDF response.
- `frontend/src/consultantSummary/LeaveLog.tsx` presents the export action and its outcome.
- `frontend/src/system/download.ts` starts and cleans up the browser download.
