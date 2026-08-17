# Leave Years and Employment Dates

## The short version

A **leave year** is the fixed period whose entitlement and leave records are being managed. In the
reference workbook it runs from **29 August 2025 to 28 August 2026**. Both dates are included.

The optional **employment start** and **employment end** fields answer a different question: was the
consultant employed for only part of that leave year?

| Situation | Leave Year Start/End | Employment Start/End |
| --- | --- | --- |
| Employed for the whole year | Enter the normal leave-year dates | Leave both blank |
| Joins on 1 January | Keep the normal leave-year dates | Enter 1 January as Employment Start |
| Leaves on 31 March | Keep the normal leave-year dates | Enter 31 March as Employment End |

Employment dates do not create a second kind of year. They simply shorten the part of the leave year
used by the later entitlement calculation. When both are blank, the application uses the complete
leave year.

## Why the workbook does not show them

The supplied workbook is a worked example for a consultant covered for the full leave year, so it
only needs the annual leave-year dates. The calculation engine also has to handle somebody joining
or leaving during a year; these optional fields supply that missing information without changing the
ordinary workbook-style workflow.

## What this slice does now

The operator can create and edit a leave year inside the selected consultant workspace. The backend:

1. stores its inclusive start and end dates in SQLite;
2. stores optional in-year employment boundaries;
3. prevents two leave years for the same consultant from overlapping;
4. records create and edit events in append-only audit history; and
5. returns the saved records after the application restarts.

This slice does **not** calculate entitlement yet. A later slice will pass the leave-year bounds and
the clipped employment period into `backend/src/leave_calculation`. In that flow, blank employment
dates mean "use the leave-year boundary".

## Files to follow

- `backend/src/leave_years/models.py` describes the stored fields.
- `backend/src/leave_years/schemas.py` checks dates received from the API.
- `backend/src/leave_years/service.py` reads, writes, prevents overlaps, and records history.
- `backend/src/leave_years/router.py` exposes the HTTP endpoints.
- `frontend/src/leaveYears/` contains the form, selected-year panel, types, and API calls.
- `backend/tests/test_leave_years.py` is executable documentation of the main behaviours.

The workbook's Job Plan `From` and `To` dates are not employment dates. They describe when a
particular job plan applies and will be stored separately in the job-plan slice.
