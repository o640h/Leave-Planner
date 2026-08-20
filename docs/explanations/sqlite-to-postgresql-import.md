# SQLite to PostgreSQL Import

The one-time import transfers an existing Leave Planner SQLite database into the initial private
PostgreSQL workspace. It is a server-owner command, not a browser upload or an ordinary Admin
setting. The hosted Admin account, password, sessions, workspace membership, and authentication
security events remain owned by PostgreSQL and are never replaced by SQLite values.

## Safety boundary

The command verifies the selected file with SQLite's integrity check and requires the Leave Planner
metadata tables. It then creates and verifies an online SQLite backup. All source migrations and
reads use a disposable working copy of that backup; the selected database and verified backup remain
unchanged.

The PostgreSQL destination must already be migrated to the current schema and must contain exactly
one Admin, one workspace, and that membership. Every business and reference table must be empty. The
command refuses to merge with existing consultant data because silent identifier remapping would
make audit and calculation reconciliation harder to prove.

## Imported data

The transfer preserves business identifiers for consultants, leave years, job plans and days,
entitlement recommendations and applications, carry-forward, holiday calendars and corrections,
holiday treatments, leave bookings and daily deduction snapshots, and domain audit events. Root
records and audit events are assigned to the destination workspace. A historical audit event that
had an authenticated actor is mapped to the destination Admin; system-import history remains
system-attributed.

## Atomic and restart-safe operation

Source validation, backup, migration of the working copy, and source-summary calculation happen
before the PostgreSQL transaction. The destination transaction obtains one PostgreSQL advisory lock,
checks the empty-workspace boundary, inserts each table in foreign-key order, advances sequences,
and reconciles the imported result before committing.

The same transaction stores the SHA-256 fingerprint of the verified source backup. A failure before
commit rolls back every imported row and the marker. A rerun after commit recognises the same
fingerprint and reports that the import already completed. A different source fingerprint is
rejected.

## Reconciliation

The command compares source and destination table counts and calculates every consultant-year
summary through the existing application services. The comparison covers job-plan periods,
recommendation and applied entitlement, DCC/SPA carry-forward, dated public holidays, booking-day
snapshots, projected/confirmed/actual balances, weekday counts, leave-log rows, PDF row totals,
warnings, and domain audit details. Timestamps are excluded from the summary digest because SQLite
and PostgreSQL represent timezone metadata differently; their persisted rows and counts are still
retained.

The PostgreSQL integration test imports the complete golden worked example and confirms the expected
entitlement, used leave, remaining leave, PDF response, preserved identifiers, and safe repeated
execution.

## Command

Run this from `backend` with the project-root environment active. The deployment environment must
already provide `LEAVE_PLANNER_DATABASE_URL` through its protected server-side secret configuration;
do not paste the PostgreSQL password into shell history:

```powershell
$env:PYTHONPATH = (Resolve-Path "src").Path
uv run --active --no-sync python -m database_transfer --source "C:\Path\leave-planner.sqlite3"
```

The optional `--backup-directory` selects where the verified pre-import backup is retained. Without
it, the command creates `leave-planner-import-backups` beside the selected database. Do not delete the
original SQLite database or the verified backup after acceptance; keep both read-only until the
hosted deployment and off-device PostgreSQL backup have passed their later acceptance tasks.
