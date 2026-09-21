# Hosted Access and Security Design

## Initial Outcome

The development website has one password-only account named `Admin`. Successful login grants full
access to one private Leave Planner workspace. The sign-in form asks only for the password because the
account name is fixed and visible. There is no registration, email identity, invitation, MFA, or
self-service password recovery in this stage.

This is a genuine account and session boundary, not a hard-coded page password. The database retains
separate user, workspace, and membership records so later individual administrators and restricted
members can be added without changing ownership of existing leave data.

The shared account has one accepted limitation: every authenticated application change is attributed
to `Admin`, not to a particular person. Changing the password must revoke every existing session.
The operator selected a 10-character minimum for this development stage. Review that minimum and the
chosen password before external exposure because the shared account has no second factor.

## Existing Application Boundary

The current FastAPI application creates one SQLAlchemy transaction per API request through
`backend/src/dependencies.py`. Routes pass that session directly to small domain services. Consultant
records are the root of most current data: leave years belong to a consultant, and job plans,
entitlement, carry-forward, bookings, holiday treatments, summaries, and leave logs flow through a
leave year. `backend/src/audit.py` records the affected consultant and change, but it has no actor or
workspace yet.

The React client sends requests through `frontend/src/api/client.ts`. This is the single place to add
same-origin credentials, CSRF headers, and expired-session handling. `App.tsx` is the composition point
for choosing between the login screen and the authenticated workspace.

Authentication and workspace scoping wrap these existing flows. They do not change calculation
inputs, Decimal handling, entitlement recommendations, applied entitlement, booking snapshots, or
balance derivation.

## Persisted Model

### `users`

The table initially contains exactly one application-managed row:

- stable primary key;
- display name `Admin`;
- Argon2id password hash;
- enabled/disabled state;
- password version;
- created, password-changed, and disabled timestamps.

There is no email column or operator-entered username in the initial API. The model may gain individual
login identifiers later through a new migration; the shared row must retain its stable identity for
historical audit records.

### `workspaces`

The table initially contains one private Leave Planner workspace:

- stable primary key;
- internal name;
- created timestamp.

The name is not a security boundary. Access always comes from a persisted membership.

### `workspace_memberships`

The initial row links `Admin` to the workspace with role `admin`. The unique constraint is the user and
workspace pair. Only the `admin` role is accepted in this stage. Later roles require an explicit
migration, authorization rules, UI behaviour, and adversarial tests rather than being treated as
informal strings.

### `sessions`

Each login creates a server-managed session containing:

- a stable primary key and user foreign key;
- a hash of a cryptographically random opaque browser token;
- a hash of a separate CSRF token;
- creation, last-seen, absolute-expiry, and revocation timestamps;
- the password version current at login.

Only hashes are stored so a database read does not immediately provide usable browser credentials.
A session is invalid when expired, revoked, attached to a disabled user, or created under an older
password version. The initial default is a non-persistent browser cookie with a 12-hour absolute
server-side lifetime; later operational experience may shorten it.

### Audit actors and security events

Existing domain audit events gain the workspace and acting user identifiers plus the actor label
snapshot `Admin`. Imported historical events may use a null user with the actor label `System Import`.
This preserves the existing affected-consultant history while identifying whether a change came from
the shared account or a controlled system operation.

Authentication events do not belong to a consultant. A separate append-only security-event record
captures successful login, failed login, logout, session revocation, password change, account disable,
and account enable with redacted request context. Passwords, password hashes, session tokens, CSRF
tokens, and complete request bodies must never be logged.

## Data Ownership

The workspace directly owns consultant records. Existing descendants remain scoped transitively
through consultant and leave-year foreign keys. Queries must start from, or join back to, the
authenticated workspace rather than fetching an object by an unscoped identifier and checking it
afterward.

Workspace-owned information includes:

- consultants and their audit history;
- leave years and employment bounds;
- job plans;
- entitlement recommendations and applied entitlement;
- carry-forward;
- leave bookings and booking-day snapshots;
- public-holiday treatments;
- Trust-specific holiday corrections;
- exports and removal previews derived from those records.

The versioned England and Wales public-holiday source calendar remains global reference data. A Trust
correction belongs to the workspace. The hosted recovery API must not become an ordinary `Admin`
feature: PostgreSQL restore remains a server-owner operation introduced with the hosted backup task.

## Password Provisioning and Recovery

A server-side command creates the workspace, `Admin` user, and membership if they do not exist, then
prompts twice for the password without echoing it. It must not accept the password as a command-line
argument, place it in an environment file, generate a default password, or print it to logs.

The same command can reset the password. A reset replaces the Argon2id hash, increments the password
version, revokes all sessions, and writes a security event in one transaction. A separate deliberate
operation enables or disables the account. There is no browser recovery endpoint.

## Login and Session Flow

1. The unauthenticated browser may call health, login, and current-session endpoints only.
2. The password-only form sends the password over the same HTTPS origin in hosted environments.
3. The backend verifies the Argon2id hash, records consecutive failures in the database, and locks
   the shared account for 15 minutes after the fifth failed attempt.
4. Success creates the server-side session and returns the opaque HttpOnly session cookie plus a
   separate, JavaScript-readable CSRF cookie whose raw value is bound to the session by its stored hash.
5. The browser copies the CSRF value into a custom header on state-changing API requests. It never
   exposes or stores the session token in JavaScript storage.
6. Every protected request resolves the session, enabled `Admin` user, and workspace membership before
   entering a domain service.
7. Logout revokes the session and clears browser state. Expiry returns one consistent unauthorized
   response that sends the interface back to login without losing server data.

In hosted HTTPS environments, the session cookie uses `Secure`, `HttpOnly`, `SameSite=Strict`,
`Path=/`, no `Domain`, and the `__Host-` prefix. Local HTTP development uses a clearly separate cookie
name without `Secure`; production must fail configuration validation if secure cookies are disabled.
State-changing requests also validate the request origin. SameSite is defence in depth rather than the
only CSRF control.

The implementation follows the OWASP Password Storage, Session Management, and CSRF Prevention cheat
sheets:

- <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html>
- <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>
- <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>

## Authorization Rules

- `/api/health` and login are the only unauthenticated operations. Current-session may report that no
  session exists; logout requires an active session and CSRF validation.
- Every other API route requires an active `Admin` session and membership in the one workspace.
- Client-supplied workspace identifiers are never accepted as authority.
- Exports, audit reads, archive/delete previews, mutations, holiday corrections, and settings receive
  the same authorization checks as ordinary reads.
- Disabled or password-version-invalidated sessions fail before a database object is returned.
- The frontend hiding a control is never treated as authorization.

## Concise Threat Model

| Threat | Initial control |
| --- | --- |
| Password guessing | Operator-chosen password, Argon2id, uniform failure responses, and a persisted 15-minute lockout after five consecutive failures. |
| Shared-password disclosure | No default or logged password; manual reset revokes every session. Individual accountability is explicitly deferred. |
| Session theft | Random opaque tokens, token hashes at rest, hosted HTTPS, `Secure`, `HttpOnly`, `SameSite=Strict`, absolute expiry, and revocation. |
| CSRF | Separate CSRF token, custom request header, request-origin validation, SameSite cookie, and no state-changing GET routes. |
| Broken object authorization | Resolve authenticated membership first and scope every root query through `workspace_id`; test guessed and altered identifiers. |
| Unauthorized membership | No membership HTTP endpoint; only migrations/server commands can create the initial membership. |
| Account enumeration | The login screen has no identifier and returns one generic failure response. |
| Secret leakage | No secrets in Git, command arguments, browser storage, URLs, exports, or logs; validate hosted secret configuration at startup. |
| Database exposure | PostgreSQL stays on the private container network and is never published through the NAS or router. |
| Malicious uploads | No upload endpoint exists in this scope. A later import/upload feature requires its own validation and storage design. |
| Backup disclosure | PostgreSQL dumps are restricted and encrypted according to the hosted backup task; restore is not an application-admin action. |
| NAS loss or compromise | Encrypted off-device backup, account/session revocation, secret rotation, and documented restore/incident procedures are required before live use. |
| Destructive shared-admin action | Existing confirmations and append-only domain audit remain; events identify `Admin`, but individual attribution is unavailable by accepted design. |

## Expected Implementation Sequence

Tasks 3-6 implement this boundary end to end. Database configuration and migrations support
PostgreSQL; the fixed `Admin` user has manually provisioned credentials and revocable sessions; every
protected service resolves the private workspace membership; and the browser presents coherent
account, sign-out, expiry, authorization-denied, and unavailable-server states. PostgreSQL backup and
restore remain a separately authorised server-owner responsibility for the hosted operations task.

Expected later files include new responsibility-based authentication and workspace packages under
`backend/src`, Alembic migrations, request dependencies, settings, the central frontend API client,
an authentication screen/state boundary, and focused backend/frontend tests. Calculation packages are
not expected to change.

The demonstrable authentication path is: initialise `Admin` from the
server, see the password-only login screen, reject a wrong password without exposing detail, accept
the configured password, load the existing application, log out, and prove the old session can no
longer access any protected API. Workspace membership and domain audit identity are documented in
`private-workspace-authorization.md`; authentication and account-administration actions use the
separate security-event log.
