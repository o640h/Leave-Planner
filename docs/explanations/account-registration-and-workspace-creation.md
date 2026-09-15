# Account Registration and Workspace Creation

## Operator Outcome

Account creation and workspace creation are separate actions. A person registers one global email
identity, confirms the single-use verification link, and then signs in. That sequence does not create
a workspace or grant access to somebody else's workspace.

A signed-in account with no memberships sees a neutral onboarding screen. **Create Workspace** opens
a short naming dialog; confirmation atomically creates one empty workspace, makes the current account
its Owner, and selects it in the current session. The same action is available under **Settings >
Workspace** for an account that intentionally needs another workspace.

## Registration Modes

`LEAVE_PLANNER_REGISTRATION_MODE` accepts:

- `closed`: no public account-creation action or route;
- `invitation_only`: no general account creation; the invitation-bound flow is added with membership
  invitations; or
- `open`: the sign-in page exposes **Create Account**.

The default is `open` for local development and production. Invitation Only remains available for a
private rollout, and Closed remains an operational shutdown control. Workspace invitations remain
the only way to join somebody else's workspace regardless of registration mode.

The registration endpoint uses the existing account-action throttle and exact-origin protection. It
returns a generic success message for an existing active address and does not disclose whether that
account exists. A new account remains pending and cannot sign in until the emailed verification token
is consumed. Tokens are hashed, expire after 24 hours, and are single use. Passwords use the shared
minimum of eight characters and the existing Argon2id storage boundary.

## Workspace Creation Boundary

`POST /api/workspaces` requires an authenticated session, matching CSRF cookie/header, and exact
origin. The server counts only Owner memberships against
`LEAVE_PLANNER_OWNED_WORKSPACE_LIMIT`, which defaults to three. Memberships in workspaces owned by
other people do not consume that allowance.

Creation writes the workspace and sole Owner membership in one request transaction, updates the
account's last workspace and the current session selection, and records a security event. A new
workspace contains no consultants, bookings, Trust corrections, memberships, or tenant audit
history copied from any other workspace. PostgreSQL creation preallocates the workspace ID and binds
that ID transaction-locally before either row is inserted, so the existing row-level security policy
still fails closed outside this explicit path.

## Local Acceptance

To exercise account creation locally, set this in `backend/.env`, restart FastAPI, and open the Vite
site through `http://localhost:5173`:

```dotenv
LEAVE_PLANNER_REGISTRATION_MODE=open
LEAVE_PLANNER_OWNED_WORKSPACE_LIMIT=3
```

With the development outbox provider, submit **Create Account**, then read the verification URL from
`http://localhost:5173/api/auth/development/email-outbox`. With Resend configured, use the link in
the delivered message instead. After confirmation and sign-in, create the first workspace from
onboarding. Open **Settings > Workspace** to create a second workspace and confirm the workspace
selector can switch between them.

The NAS deployment uses:

```dotenv
LEAVE_PLANNER_REGISTRATION_MODE=open
LEAVE_PLANNER_OWNED_WORKSPACE_LIMIT=3
```

The ownership limit is per account. It prevents one ordinary account from creating an unlimited
number of workspaces, but it does not prevent automated creation of many accounts. The existing
request and account-action throttles are the current boundary; the later security and acceptance
tasks must add and verify stronger abuse and capacity controls for the already-open registration
surface.

## Calculation Boundary

Registration and empty-workspace creation do not invoke or change leave calculations. They create no
consultant, leave-year, job-plan, entitlement, holiday, carry-forward, booking, deduction, or ledger
records.
