# Safe Removal

Removal is intentionally different for consultants, leave years, and job plans. The application
protects history while still letting the operator correct setup mistakes.

## Consultant archive

A consultant is **archived**, not deleted. Archiving:

- removes the consultant from the active directory;
- retains every leave year, job plan, entitlement record, and audit event; and
- requires the consultant's full name as confirmation.

The record remains addressable by its identifier so a later archive-management screen can restore
or inspect it without reconstructing history.

## Leave-year deletion

A leave year can currently be deleted when it only contains setup information. Before confirmation,
the application reports how many job plans, recommendation snapshots, and applied entitlement
records belong to it. The operator must enter `DELETE` exactly.

The leave year and its owned setup records are removed, but a final audit event records the dates and
reported consequences. Once persistent leave bookings are introduced, any year containing historical
leave must be blocked from this destructive path and retained instead.

## Job-plan deletion

Before deleting a job plan, the application checks whether the remaining plans still cover the
consultant's active leave-year period.

- With complete remaining coverage, a calculated entitlement recommendation can be refreshed.
- A manual applied entitlement is never silently overwritten.
- If deletion creates a coverage gap, the existing applied entitlement is preserved and returned as
  `needs_attention` rather than presenting a misleading new calculation.

The deleted plan's full stored values and the coverage result are written to the audit history.

## Frontend flow

Each removal action first requests an impact preview. The confirmation dialog shows those consequences
and enables its final action only after the exact confirmation text is entered. The normal editor does
not hide these consequences behind a generic confirmation popup.

