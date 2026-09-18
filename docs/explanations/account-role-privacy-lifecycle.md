# Account, Role, Privacy, and Lifecycle Boundary

## Purpose

This checkpoint fixes the authority and privacy rules that the later Phase 7 slices must implement.
It changes no application behaviour. The current password-only `Admin`, single-membership resolver,
leave calculations, applied entitlement, booking snapshots, and balance derivation remain unchanged
until their owning tasks deliberately replace or extend them.

The first named Owner will start with a new empty workspace and will not inherit the shared `Admin`
identity or its legacy workspace. The transition command introduced later must collect and verify
the actual account details without writing them to source control or logs. It may remove the legacy
workspace only after proving that no business data would be lost; otherwise it must stop for an
explicit migration decision.

## Existing Boundary and Future Request Flow

Today, a browser session resolves the fixed `Admin` user and exactly one `admin` membership. The
request dependency binds that workspace to the SQLAlchemy transaction before consultant roots,
Trust corrections, exports, or audit history can be accessed.

The future flow preserves that server-owned boundary:

1. The email and password authenticate one global account.
2. The opaque, hashed server-side session identifies that account.
3. The session stores the selected workspace only after the server proves a live membership.
4. The request dependency revalidates the account, session, membership, role, and active workspace.
5. The resolved workspace and authority are bound to the database transaction.
6. Domain services operate only inside that context; a client-supplied workspace or record ID never
   grants access.

Zero memberships leads to onboarding. One membership selects automatically. Multiple memberships
use the last still-authorised selection and expose a visible selector. A removed or disabled
membership invalidates that workspace selection immediately.

## Permission Matrix

| Capability | Owner | Admin | Member |
| --- | --- | --- | --- |
| Use the complete consultant planner | Yes | Yes | No |
| Create, edit, archive, or remove consultant data | Yes | Yes | No |
| Maintain leave years, job plans, entitlement, holidays, carry-forward, and bookings | Yes | Yes | No |
| View calculations, entitlement, job plans, and balances | Yes | Yes | Own consultant only |
| View the linked consultant's restricted information | Yes | Yes | Yes |
| Request or withdraw bookings and request cancellations for the linked consultant | Yes | Yes | Yes |
| Review requests and create authoritative bookings | Yes | Yes | No |
| Invite, link, unlink, or remove ordinary Members | Yes | Yes | No |
| Invite, promote, demote, or remove Admins | Yes | No | No |
| Transfer workspace ownership | Yes | No | No |
| Close or recover the workspace | Yes | No | No |

There is exactly one Owner per workspace. An Owner cannot leave, be removed, be demoted, delete their
account, or close their last recovery route until another eligible verified member accepts ownership
in the same atomic operation. Admin authority is intentionally sufficient for day-to-day operation
and ordinary Member administration, but never for changing who controls the workspace.

A Member membership may link to at most one consultant in the same workspace. Until linked, the
Member sees onboarding and a waiting-for-access state only. Membership in one workspace grants
nothing in another, even when the same global account belongs to both.

## Member Privacy Boundary

A linked Member receives a complete read-only version of their own consultant workspace. This
includes identity, leave-year and employment dates, job plans and deduction patterns, calculated and
applied entitlement explanations, carry-forward, balances, bookings, request history, and applicable
policy material. Every job-plan control and authoritative number remains non-editable. The Member may
request bookings, withdraw pending requests, and request cancellation of an existing booking through
the dedicated request workflow. They cannot create, edit, or cancel authoritative planner records
directly.

On the shared Planning wallchart a Member may see only:

- each colleague's display name;
- the dates covered by a leave booking and its Requested or Approved state; and
- public-holiday context.

The Member wallchart must not expose another consultant's leave category, DCC/SPA split, hours,
entitlement, balances, job plan, employment information, notes, calculation detail, record identifiers,
exports, or audit events. The server must shape this restricted response; hiding fields or controls in
React is not an authorization control.

The implemented Member surface uses a separate `/api/member` router guarded by an exact Member-role
dependency. It derives the consultant identifier from the revalidated membership rather than from a
client parameter. Its read-only workspace contract removes consultant, job-plan, booking,
recommendation, application, carry-forward, and audit identifiers before serialization. The shared
wallchart does not reuse the operator planning response: its database query selects only workspace
consultant names and overlapping non-cancelled booking dates and states, then returns those restrained
status blocks plus the resolved public-holiday calendar. The same-workspace consultant link remains protected by
the composite database foreign key and every query is constrained to the transaction-bound
workspace. The existing operator routers continue to reject Member sessions.

Task 8 includes the Member's own authoritative bookings. Task 9 will allow the Member to create a
Requested booking for their linked consultant; review changes that same record to Approved or
Cancelled rather than creating a second request record. Until that slice exists, the Member workspace
contains no controls that can create, change, cancel, or export planner records.

## Registration, Invitations, and Recovery

Production begins in `Open` mode so anyone can create and verify a global account. Registration never
grants access to an existing workspace: joining one still requires an invitation from that
workspace. `Invitation Only` remains available for a private rollout and `Closed` for an operational
shutdown. The later security and capacity gate hardens and verifies the open surface rather than
enabling it for the first time.

An account may initially create no more than three workspaces it owns. This is a deployment setting,
not a commercial domain rule. Memberships in workspaces owned by somebody else do not count. Raising
the limit is an explicit NAS capacity decision. This per-account limit is not a defence against an
attacker registering many accounts; rate limits and the later abuse controls remain necessary.

Invitation tokens expire seven calendar days after issue. Password-reset tokens expire one hour
after issue. Both are cryptographically random, stored only as hashes, single use, and revoked when
superseded or completed. Resending an invitation revokes its previous token. Completing a password
reset increments the password version and revokes every existing session for that account.

Verification, invitation, and recovery responses must not reveal whether an email address or account
exists. Invitations are bound to one canonical email and workspace; a signed-in account with a
different canonical email cannot accept them.

## Account Deletion and Audit Retention

Account deletion is a deliberate, irreversible operation rather than a way to evade workspace
ownership or audit history. Before deletion, the account must transfer every workspace it owns.
Deletion then revokes every session, removes active memberships and outstanding one-time tokens, and
removes the email and display name from the active identity.

Historical domain and security events retain a stable opaque actor reference needed to explain who
performed an action, but deleted identities are presented through a non-identifying tombstone such
as `Deleted Account`. Complete email addresses are never copied into event details. The later schema
and migration must preserve event meaning without making an active login recoverable from the
tombstone.

Workspace audit history is retained while the workspace exists and through its closure-recovery
period. Permanent workspace removal deletes the workspace-owned operational and audit data through
the separately authorised purge path, subject to the documented PostgreSQL backup-retention window.
The organisation's formal retention period remains a governance decision that must be confirmed
before `Open` registration or live employment data is enabled; the application must not invent one.

## Workspace Closure and Recovery

Only the Owner may close a workspace. Closure requires recent re-authentication, an impact preview,
and explicit confirmation. It enters a 30-day recoverable state rather than immediately deleting
records. Ordinary memberships cannot read or mutate a closed workspace, it cannot remain selected in
a session, and pending invitations and requests are revoked.

During those 30 days, the same Owner may recover the complete workspace after re-authentication.
After the period, permanent removal is a separately authorised server operation, not an ordinary
application button. The removal must cover workspace-owned consultants, leave records, corrections,
membership state, invitations, requests, audit history, and derived exports as one reviewed action.
Global accounts and their memberships in other workspaces are unaffected.

Backups can retain already-purged information until the documented NAS backup-retention window
expires. The interface and operator guidance must say this plainly. NAS-only storage remains an
accepted limitation and does not protect against whole-NAS loss.

## Email Delivery Failure

The NAS database remains authoritative when the delivery provider is unavailable. Existing accounts,
sessions, workspaces, and planner operations continue normally. An invitation, verification, email
change, or password reset that requires proof of mailbox control does not complete merely because a
message could not be delivered.

The application retains the pending operation safely, records a redacted failure, exposes a clear
pending or delayed state, and retries without issuing duplicate authority. Resending revokes any
superseded token. No membership is granted and no password is changed until the corresponding valid
token is presented. Documented server-side recovery remains available to the deployment operator;
there is no permanent emergency account or plaintext-token fallback.

## Data Map

### Authoritative Data Retained on the NAS

- global account ID, canonical and display email, display name, verification and security state;
- Argon2id password hash, password version, MFA state, and hashed recovery codes;
- workspaces, roles, memberships, consultant links, and ownership history;
- hashed session and one-time token values, expiry, revocation, throttling, and lockout state;
- consultants, leave years, job plans, entitlement, carry-forward, bookings, requests, and balances;
- workspace corrections, audit and security events, and provider-neutral delivery state; and
- mail purpose, redacted recipient reference, creation/attempt/completion timestamps, retry state,
  and provider message identifier.

Raw passwords, session tokens, CSRF tokens, one-time tokens, and MFA recovery codes are never logged.
Only token hashes or reviewed password hashes are persisted.

### Limited Data Processed by the Delivery Provider

- recipient email address;
- dedicated sender address;
- generic subject and transactional message body;
- the expiring action link while the message is delivered;
- provider message identifier, timestamps, and delivery status; and
- provider-standard transport and abuse metadata.

Invitation messages contain only the minimum account/workspace invitation context. They contain no
consultant identity, employment information, leave dates, request content, entitlement, balance,
job-plan information, notes, audit history, password, or authentication secret other than the
single-use action link. The provider is a delivery processor, never the identity provider or source
of account or membership truth.

## Calculation and Operator-Control Boundary

These rules wrap the planner; they do not alter its calculations. Owner and Admin use the existing
operator workflows. Calculated entitlement remains an explained recommendation, manually applied
entitlement remains separately persisted, and booking approval must continue through the established
preview, daily-deduction snapshot, ledger, warning, and audit flow.

A Member request is not a booking and cannot affect a balance. Only a later authorised Owner/Admin
approval may atomically create the authoritative booking or apply a requested cancellation through
the established cancellation flow. Submission and withdrawal create durable, workspace-scoped
notifications for Owners/Admins; WebSocket updates may later prompt an immediate refetch but never
replace the stored request or notification. No role may bypass Decimal serialization, effective-dated
job plans, public-holiday treatment, applied entitlement, or retrospective-change controls.

## Implementation Route

This checkpoint changes `Implementation.md` and this explanation only. Later slices are expected to
change the existing responsibility-based authentication and workspace packages, Alembic migrations,
request dependencies, settings, central frontend API boundary, authentication screens, and focused
backend/frontend tests. Calculation packages should remain unchanged unless a later request workflow
needs to call their existing public behaviour.

## Acceptance Scenarios for Later Tasks

The implementation is not complete until automated and rendered checks prove at least these cases:

1. The first named Owner receives a new empty workspace without inheriting the shared Admin identity
   or any legacy consultant, entitlement, booking, correction, or audit data.
2. An Admin can operate the planner and manage Members but cannot appoint an Admin, remove the Owner,
   transfer ownership, or close the workspace.
3. A linked Member sees the complete read-only view of their own consultant, can request bookings and
   cancellations, and sees only the restricted shared wallchart. Owners/Admins receive durable
   notifications. An unlinked Member sees no consultant or leave data.
4. A seven-day invitation and one-hour reset work once, fail after expiry or revocation, and do not
   disclose account existence.
5. A person can own up to the configured workspace limit, and every additional workspace starts
   empty and isolated.
6. Ownership transfer prevents an ownerless or double-owned workspace under concurrent requests.
7. Account deletion revokes access and removes active identifiers while historical events retain a
   non-identifying actor reference.
8. Workspace closure blocks access, permits Owner recovery for 30 days, and does not affect another
   workspace or account.
9. A mail-provider outage grants no authority, corrupts no NAS data, and leaves existing sign-in and
   planner use available.
10. Guessed IDs, altered payloads, stale sessions, sockets, exports, errors, searches, and timing do
    not disclose records or presence across workspaces.
