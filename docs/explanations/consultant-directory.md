# Consultant Directory

The consultant directory replaces the name and post-title fields repeated at the top of every workbook. It creates one reusable record for each person; leave years, job plans, entitlement, and leave entries will be attached in later slices.

## What the operator can do

- See all consultants in alphabetical order.
- Add a consultant with a required **Consultant Name** and optional **Post Title**.
- Select an existing consultant and edit those fields.
- Close and reopen the application without losing the records.

The directory deliberately does not contain specialty, appointment date, service-start date, or leave-year dates. Those facts are not part of the workbook's identifying header and will be introduced only by the later calculation workflow that needs them.

## How a change moves through the application

1. `ConsultantForm.tsx` holds the two editable values.
2. `ConsultantDirectory.tsx` sends a create or update request through `consultants/api.ts`.
3. `consultants/router.py` accepts the request through a Pydantic schema.
4. `consultants/service.py` reads or writes the SQLAlchemy `Consultant` record.
5. The request-scoped database session commits when the API call succeeds.
6. The API returns the saved record and the directory updates immediately.

On startup, Alembic applies migration `0002`, which creates the `consultants` table if it does not already exist. SQLite data is stored in the configured Leave Planner data directory rather than in frontend memory.

## Validation boundary

Validation is intentionally small and happens at the API boundary:

- the name cannot be blank and is limited to 200 characters;
- the optional post title is limited to 200 characters;
- a blank post title is stored consistently as `null`.

The backend does not repeat these checks in its trusted service code. Browser `required` and `maxLength` attributes provide immediate guidance, while the API remains the final source of truth.

## Files to change later

- Add a persisted consultant field in a new Alembic migration and `models.py`.
- Add its request/response definition in `schemas.py`.
- Read or write it in `service.py`.
- Add the matching field to `types.ts` and `ConsultantForm.tsx`.
- Extend the backend API test and frontend workflow test.

Calculation-specific dates should not be added here merely for convenience. They belong with the leave-year or entitlement setup that explains why the operator is being asked for them.
