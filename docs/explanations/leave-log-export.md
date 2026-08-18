# Leave Log Export

## Operator outcome

The expanded Leave Log can create a clean A4 PDF for the selected consultant and leave year. The
document includes consultant identity, the inclusive leave-year dates, every on-screen leave-log
entry, booking state, DCC and SPA deductions, total hours, a generated timestamp, page numbers, and
reconciled totals. Multi-page tables repeat their column headings.

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

## Safe Save As flow

The export endpoint creates PDF bytes in memory and never accepts or writes an operator-provided
filesystem path. The React interface retrieves those bytes and passes them to the packaged desktop
bridge. The bridge:

1. validates the suggested filename and PDF payload;
2. opens the native Windows Save As dialog every time;
3. treats cancellation as an ordinary outcome;
4. writes to a temporary file in the selected directory; and
5. atomically replaces the chosen destination only after the complete PDF has been written.

The browser development view cannot save the report because it has no trusted native bridge. This
is intentional: the supported installed workflow always asks the operator to choose the filename
and destination.

## Files to follow

- `backend/src/consultant_year_summary/leave_log.py` builds shared leave-log rows.
- `backend/src/consultant_year_summary/report.py` creates the multipage ReportLab PDF.
- `backend/src/consultant_year_summary/router.py` exposes the in-memory PDF response.
- `backend/src/desktop_shell/launcher.py` owns the native Save As dialog and final file write.
- `frontend/src/consultantSummary/LeaveLog.tsx` presents the export action and its outcome.
- `frontend/src/desktop/api.ts` encodes PDF bytes for the local JavaScript-Python bridge.
