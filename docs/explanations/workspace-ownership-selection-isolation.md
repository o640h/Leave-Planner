# Workspace Ownership, Selection, and Database Isolation

## Operator Outcome

One email account can now hold Owner, Admin, or Member memberships in more than one private
workspace. A sole membership opens automatically. Multiple memberships use the last still-authorised
selection; if there is no valid previous selection, the browser asks the person to choose before any
planner request runs. The selector remains visible when more than one workspace is available.

An account without a membership sees the workspace-setup state. This is deliberate preparation for
the first-Owner and registration slices; it does not create a workspace implicitly. Owner and Admin
memberships can use the existing operator planner. A Member membership is recognised but cannot enter
that full-access planner. The restricted Member interface and APIs remain owned by the later read-only
Member slice.

## Persisted Authority

`workspace_memberships` accepts exactly `owner`, `admin`, and `member`. A partial unique index permits
at most one Owner row per workspace. Workspace creation and later ownership transfer must create or
retain that single Owner in the same transaction. The empty clean-start scaffold is the only temporary
ownerless state; the first-Owner transition replaces it before production workspace use.

A membership may link to one consultant only when its role is Member. The composite foreign key from
`(workspace_id, linked_consultant_id)` to `(consultants.workspace_id, id)` makes a cross-workspace link
invalid in both SQLite and PostgreSQL. Owner and Admin memberships cannot carry a consultant link.

`users.last_workspace_id` remembers the last authorised choice across sign-ins.
`user_sessions.active_workspace_id` is the authority for the current browser session. Neither value
grants access by itself: every protected request reloads the membership for the authenticated account,
selected workspace, and current role. Removing a membership therefore invalidates that selection on
the next request without signing the person out of unrelated workspaces.

## Request and API Flow

Login and `GET /api/auth/session` return the account and workspace context together. This avoids a
second discovery request and prevents the frontend from learning that setup is incomplete through a
failed consultant query. The context contains only the signed-in account's memberships, workspace
names, roles, optional own-consultant link, current selection, and one of these states:

- `active`: a live membership backs the selected workspace;
- `selection_required`: memberships exist but none is selected; or
- `onboarding`: the account has no membership.

`POST /api/workspaces/active` accepts a workspace ID as lookup input. It is protected by the existing
session, same-origin, and CSRF checks. The server changes the session only after finding that exact
account/workspace membership; guessed or foreign IDs return the same not-found response and grant no
authority.

Existing planner routers now require the separate operator-workspace dependency. It admits Owner and
Admin only. The more general membership dependency is retained for future restricted Member routes.

## PostgreSQL Row-Level Security

The request transaction binds two transaction-local PostgreSQL settings after authentication:

- `leave_planner.user_id` before membership discovery; and
- `leave_planner.workspace_id` only after the selected membership is revalidated.

Row-level security is enabled on workspaces, memberships, consultants, Trust holiday corrections, and
domain audit events. Membership discovery may see only rows belonging to the bound account; workspace
roots may see or change only rows matching the bound workspace. Missing settings evaluate to no
authority. The runtime database login is not a table owner, superuser, or `BYPASSRLS` role, so an
ordinary unscoped query returns no private roots and an unscoped mutation is rejected. Indexed
`workspace_id` and `user_id` columns support the policy lookups.

The migration login remains the schema owner and is not used by the application. New and existing
objects receive explicit runtime grants so deployment does not depend only on default privileges.
SQLite keeps the application-level binding and constraint tests but is not treated as evidence for
database-enforced row isolation.

## Backup and Restore Roles

The NAS database initialization and release process maintain two no-login operational roles:

- `leave_planner_backup` has read-all-data and `BYPASSRLS` solely so a complete verified dump does not
  silently omit tenant rows; and
- `leave_planner_restore` may own a generated verification database and recreate the archive there.

The host's separately authorised PostgreSQL administration connection assumes these roles through
`pg_dump --role` and `pg_restore --role`. Restore verification never targets the live database. The
idempotent `ConfigureDatabaseRoles.sh` runs before each release backup so an established NAS volume
receives the same roles as a new installation. The application credential cannot migrate, back up,
restore, create databases, or bypass RLS.

## Calculation Boundary

No entitlement, PA, public-holiday, deduction, carry-forward, booking snapshot, ledger, warning, or
balance rule changed. Workspace resolution completes before the existing consultant root is loaded;
after that point the established calculation and application-service call order is unchanged.

## Verification

Focused tests cover automatic and explicit selection, last-selection persistence, guessed workspace
IDs, Member denial from the operator planner, duplicate Owners, cross-workspace consultant links, and
the absence of implicit service access. The opt-in PostgreSQL proof inspects all RLS-enabled roots,
assumes the non-owner application role, confirms an unbound query sees no consultants, confirms a
bound workspace sees only its row, and confirms an unbound insert is denied. Frontend coverage proves
that selection happens before the consultant workspace mounts and that the active selector remains
visible afterward.
