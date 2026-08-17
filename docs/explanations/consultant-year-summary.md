# Consultant-Year Summary

The consultant-year summary is the application's equivalent of the workbook's `Master` sheet. It does not store a second balance or perform a separate entitlement calculation. It gathers the facts and calculated results that already exist and presents them in one response and one screen.

## What the summary reads

The summary API reads, in order:

1. The consultant and selected leave year.
2. Every job plan that overlaps that leave year.
3. The current entitlement recommendation and the entitlement actually applied.
4. Carry-forward for the selected year.
5. Public holidays, leave bookings, daily deduction snapshots, and the three balance views.
6. Recent audit events for the consultant.

The implementation is in `backend/src/consultant_year_summary/service.py`. Its API route is in `backend/src/consultant_year_summary/router.py`. The React display is in `frontend/src/consultantSummary/`.

## Annual leave by job plan

The workbook starts with the complete annual entitlement, including public holidays, and divides it between job-plan periods by calendar days. For each period:

```text
period leave = complete annual entitlement x period calendar days / active leave-year days
```

The result is then split using that period's contracted DCC and SPA PA proportions:

```text
DCC leave = period leave x DCC PA / total PA
SPA leave = period leave x SPA PA / total PA
```

For the supplied example, `291.368` hours becomes a 337-day result plus a 28-day result. The two period results add back to `291.368` hours. These are the figures shown under **Annual Leave by Job Plan**.

This is intentionally separate from the date-specific public-holiday detail in the entitlement panel. The period table reproduces the familiar workbook presentation. The entitlement detail explains which dated holidays created the public-holiday addition. They are two views of the same total, not two additions.

## Leave position

Balances are derived each time the summary is requested:

```text
available = applied entitlement + carry-forward
used = public-holiday deductions + booking deductions
remaining = available - used
```

Carry-forward is added to DCC, matching the workbook. A booking never changes entitlement; its saved daily deductions change the used and remaining figures.

The three tabs answer different questions:

- **Projected** includes Planned, Approved, and Taken leave.
- **Confirmed** includes Approved and Taken leave.
- **Actual** includes Taken leave only.
- Cancelled leave is retained in history but deducts nothing.

## Weekday counts

The weekday row counts each applicable public-holiday date and each Taken booking date with a positive deduction once. It does not copy the workbook's overlapping `COUNTA` formulas because those ranges double-count many cells. The corrected reference counts are 14 Mondays, 12 Tuesdays, 12 Wednesdays, 2 Thursdays, and 2 Fridays.

## Stored data and operator control

The summary itself has no database table. Consultant details, leave years, job plans, applied entitlement, carry-forward, holidays, bookings, booking-day snapshots, and audit events remain stored in their existing SQLite tables. The summary is read-only composition over those records.

Changes are still made in their owning screens. This keeps entered facts separate from calculated output and avoids a second editable copy of the same value.
