# First Owner Workspace

## Outcome

The first Owner is established by an explicit server-operator command, never by visiting a public
route. The command either creates a verified named account or verifies the current password of an
existing verified account. It then replaces the migration-era empty workspace scaffold with a new,
empty workspace and grants exactly one Owner membership.

Sign-in remains side-effect free. Once setup is complete, a normal email-and-password login finds one
membership, selects it automatically, and opens the existing planner. No calculation, entitlement,
job-plan, booking, or balance behaviour changes.

## Transaction and clean-start boundary

`workspaces.service.create_initial_owner_workspace` owns the transaction's domain rules. Before its
first write it checks that there are no memberships and no consultant, Trust-correction, or workspace
audit rows. Any such data stops setup. The old empty workspace row is deleted rather than renamed or
assigned, so the named Owner cannot inherit a prior tenant boundary.

Account creation or password verification, scaffold removal, new workspace creation, Owner
membership, last-workspace selection, security event, and revocation of pre-setup sessions all use
the caller's single database transaction. An error rolls the whole operation back. Re-running the
command with the same Owner credentials and workspace name verifies the completed setup without
creating another workspace.

The command does not delete global account security history. That history belongs to the named
account, not to the discarded workspace, and contains no inherited consultant or leave information.

## Local command

From `backend` in PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path "src").Path
..\.venv\Scripts\python.exe -m authentication.account_admin create-owner
```

For a new account, enter its email, display name, password twice, and workspace name. If the account
already exists, enter its email, current password, and workspace name. The existing password is
verified and is not changed.

All active sessions for that account are revoked during the transition. Sign in again at
`http://localhost:5173`. The `reset-password`, `disable`, and `enable` server operations remain
available for recovery; there is no permanent emergency login.

## NAS command

Run the command from the repository root or current release directory after the database migration:

```powershell
docker compose --file deploy/compose.yml --file deploy/compose.cloudflare.yml run --rm migrate python -m authentication.account_admin create-owner
```

The `migrate` service supplies the narrowly controlled migrator database connection needed to create
the initial unbound workspace despite application row-level security. The command refuses to run in
production as `leave_planner_application`. It does not require the Resend secret and never accepts a
password in command arguments.

## Acceptance

Focused tests cover new and existing accounts, exact Owner membership, an empty tenant boundary,
idempotent verification, wrong-password and legacy-data rollback, two simultaneous browser sessions,
single-session logout, and all-session revocation during password recovery. PostgreSQL deployment
acceptance should run the interactive command through the `migrate` service, sign in through the
public HTTPS origin, and confirm the empty planner before real consultant data is entered.
