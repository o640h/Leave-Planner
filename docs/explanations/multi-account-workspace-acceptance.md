# Multi-Account and Workspace Acceptance

## Outcome

The application keeps account identity, workspace authority, consultant data, live collaboration,
and recovery operations behind the same workspace boundary. The acceptance run on 21 September
2026 used separate Owner, Admin, and Member identities against an isolated database and the built
frontend served by FastAPI.

The rendered walkthrough confirmed these visible boundaries:

- an Owner sees workspace naming, role changes, and lifecycle controls;
- an Admin can operate consultant records and manage Members, but cannot use workspace lifecycle
  controls;
- a linked Member sees only My Leave, Team Wallchart, workspace selection, Account, and the
  authenticated Policy & Guidance library; and
- all roles can switch among only the workspaces in which their account has a membership.

The browser walkthrough used synthetic local accounts. No live mailbox, production database, or
external email provider was used.

## Verified Boundaries

The automated suite covers the following acceptance paths:

| Boundary | Evidence |
| --- | --- |
| Independent Owner, Admin, and Member sessions | Three concurrent authenticated clients retain distinct roles and receive only their permitted API contracts. |
| Existing-account invitations | The invited address must be signed in, the token is single use, and accepting it selects the invited workspace. |
| New-account invitations | Registration remains pending until the mailbox verification token is consumed; only then is the claimed membership activated. |
| Invitation expiry and revocation | Expired and explicitly revoked action tokens are rejected without creating membership. |
| Promotion, demotion, removal, and ownership transfer | Owners can promote and demote non-Owners, removal clears active workspace selections, and the retained server contract changes ownership only after the nominated Admin accepts. Ownership transfer is intentionally not offered in the People interface. |
| Password and operator recovery | Verified-mailbox reset is generic, expiring, single use, and revokes every session. The server account command resets credentials and records the security change without a browser bypass. |
| Workspace selection and creation | A verified account can create an empty workspace up to the configured Owner limit; guessed workspaces cannot be selected. |
| Record and export isolation | Consultant records, leave years, bookings, holidays, searches, PDF exports, and audit data are always scoped by the active workspace. |
| Error non-disclosure | A real record in another workspace and an unknown identifier return the same status and error payload. Both execute the same indexed, workspace-scoped lookup, avoiding a separate existence path that could expose useful timing information. |
| Live updates and pointers | Only compatible views in the same workspace receive cursor data. Payloads contain a connection identifier, initial, colour index, normalised coordinates, and view token; they never contain account, consultant, leave, or workspace identifiers. |
| Stale and revoked connections | Stale writes fail with `409`; logout and workspace-context changes close affected sockets; reconnect performs a full refetch; connection and message floods are bounded. |
| Trusted client addresses | `CF-Connecting-IP` is accepted only in explicit production Tunnel mode from the private edge. Direct and local callers cannot rotate the header to evade limits. |
| Email-provider failure | Failed delivery is redacted and auditable. It does not undo an account, invitation, leave request, or workspace change that already committed. |
| Backup and restore | The automated recovery suite restores consultant-year data and protects managed backup paths. The PostgreSQL script additionally verifies identity, session, action-token, membership, and row-level-security state before accepting a restore. |

## Recovery and Deletion

Mailbox recovery is the normal account route. A reset link expires, works once, and invalidates all
existing sessions after the password changes. If the Owner cannot use the verified mailbox, the NAS
operator may use the server account command from an authenticated administrative shell. That
operation is exceptional: confirm the person's identity outside the application, record the reason,
reset or re-enable only the named account, and require the person to change the temporary password.

An empty workspace created by mistake may be deleted after exact-name confirmation. A workspace with
operational history is closed instead, becomes unavailable for normal work, and enters its 30-day
recovery period. Only the current Owner can recover it after password re-authentication. Permanent
purge is a deliberate server operation after the deadline. Member removal preserves workspace audit
history while immediately clearing that workspace from the removed account's active sessions.

Database recovery uses a verified PostgreSQL dump in the administrator-restricted NAS backup folder.
The restore drill must use the migration and restore roles, verify the required security tables and
row-level policies, and then test sign-in, workspace selection, and a foreign-workspace denial before
service returns to users. NAS-only storage remains an accepted limitation and does not protect
against loss of the complete NAS.

## Registration Decision

Open registration remains appropriate for the intended launch because account creation does not
create access to an existing workspace, mailbox verification is mandatory, account actions are
rate-limited by the trusted client address, workspace creation is authenticated and capped, and
joining another workspace still requires an invitation.

This decision assumes the production deployment uses the approved Cloudflare Tunnel boundary, the
Resend account is monitored for unusual volume, and the public origin and trusted-proxy mode remain
exactly configured. `invitation_only` is the immediate fallback if mail volume, capacity, or abuse is
unexpected; `closed` remains the emergency shutdown setting. The in-process limits reset when the
application restarts and are not a substitute for provider-side abuse monitoring.

## Deployment-Environment Check

The Windows acceptance environment has no running PostgreSQL or container daemon, so PostgreSQL-only
runtime and live restore checks are skipped locally. Before the first NAS release, run the complete
suite against the pinned PostgreSQL image, execute one backup and restore drill with synthetic data,
and confirm the Tunnel supplies the expected private peer plus `CF-Connecting-IP`. This is an
environmental deployment check, not an application-code gap.
