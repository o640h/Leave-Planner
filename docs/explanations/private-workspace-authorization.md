# Private Workspace Authorization

This document records the original single-workspace boundary. The current multi-membership selection
and PostgreSQL RLS design is documented in `workspace-ownership-selection-isolation.md`.

## Boundary

Leave Planner currently exposes one private workspace and one full-access role. The fixed `Admin`
user receives an `admin` membership when the account is created. Existing installations are
backfilled during migration: the initial workspace is created, every existing user becomes its
administrator, and existing consultant, Trust-correction, and audit roots are assigned to it.

There is no HTTP operation for creating a workspace or changing membership. Multiple users, roles,
invitations, access requests, read-only views, and leave requests remain outside this slice.

## Request Flow

Every application route first validates the server-side session, enabled user, CSRF token for a
state-changing request, and then exactly one persisted workspace membership. Missing or ambiguous
membership returns `403` before a domain service runs. The resolved user, actor label, workspace, and
role are bound to the request's database transaction; clients never submit a workspace identifier.

Consultant queries include the resolved `workspace_id`. Leave years, job plans, entitlements,
carry-forward, bookings, booking-day snapshots, public-holiday treatments, summaries, exports,
removal previews, and audit history are reached only after their consultant root has passed that
check. A guessed identifier from another workspace therefore receives the same `404` as an unknown
identifier.

Trust-specific holiday corrections also carry and query `workspace_id`. The versioned England and
Wales source calendar and its dated events remain shared reference data. SQLite recovery routes exist
only during local development and require the same membership; PostgreSQL restore remains a later,
separately authorized server operation.

## Audit Identity

New domain audit events store the workspace identifier, acting user identifier, and the `Admin`
display-name snapshot. Historical events created before authentication retain their consultant and
details, are assigned to the initial workspace, and use the non-user actor label `System Import`.
Authentication and account-management events remain in the separate security-event log.

## Verification

Adversarial API coverage checks unauthenticated, disabled, and valid-but-memberless sessions across
read, mutation, PDF export, deletion, settings, and local recovery surfaces. A synthetic second
workspace proves that its consultants, leave years, audit events, and Trust corrections cannot be
listed, read, modified, archived, exported, or removed by the initial workspace. The migration test
proves existing roots and the existing Admin are backfilled without changing calculation records.
