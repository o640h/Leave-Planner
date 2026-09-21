# Email Identity and Authentication

## Operator Outcome

Leave Planner now authenticates named people with an email address and password. Display names do not
need to be unique. The browser and API expose an opaque public account ID rather than the database
primary key.

Identity and authentication remain separate from workspace creation. An account without a membership
receives the workspace-setup state. The explicit first-Owner command can create or verify the initial
account and atomically attach it to a new blank workspace; ordinary verified accounts use the
separate authenticated Create Workspace action.

## Clean Start

The operator approved discarding the practically empty shared Admin account boundary. Migration
`0015` removes users, sessions, security events, and memberships only when consultant, Trust
correction, and domain audit tables are empty. The schema retains one empty internal workspace scaffold
with no membership or business records for the first-Owner slice. If business data exists, migration stops and reports
the occupied tables instead of deleting them.

No fake or reserved email is assigned to the old Admin. The legacy password-only route and
administration module are removed.

## Account Fields

Each account stores:

- an internal integer key used only for database relationships;
- a random 128-bit public ID represented as 32 hexadecimal characters;
- a non-unique display name;
- the operator-entered display email;
- a unique canonical email used for lookup;
- the email verification timestamp;
- pending-verification, active, disabled, or deleted security state;
- the Argon2id password hash and password version;
- persisted failed-attempt and lockout state; and
- creation, password-change, lockout, and disablement timestamps.

Email addresses are validated without a network lookup. Canonicalisation trims surrounding
whitespace, applies standards-aware normalisation, and case-folds the result. It does not remove
dots, plus tags, or apply provider-specific aliases.

## Login Request and Response

The public request is:

```json
{
  "email": "operator@example.org",
  "password": "the account password"
}
```

A successful response identifies the signed-in person without exposing the internal database key:

```json
{
  "authenticated": true,
  "user": {
    "public_id": "0123456789abcdef0123456789abcdef",
    "display_name": "Primary Operator",
    "display_email": "Operator@Example.org"
  }
}
```

Unknown email, wrong password, pending verification, disabled account, and active account lockout all
return the same status, code, and message. Unknown accounts still execute the reviewed dummy Argon2id
verification path. Security events record the result and source without copying a complete email into
event details.

Five consecutive failures lock the matching stored account for 15 minutes. The response deliberately
does not reveal that the account exists or is locked. The existing per-client HTTP rate limit remains
a second abuse boundary for unknown identifiers.

## Sessions and Passwords

Successful login retains the existing 12-hour server-side session. Only hashes of the random session
and CSRF tokens are persisted. Production cookies remain Secure, SameSite Strict, host-only, and
path-scoped; the session cookie remains HttpOnly. Unsafe requests still require the matching readable
CSRF cookie/header and same-origin validation.

Password reset increments the password version and revokes every session. Disabling or deleting an
account also revokes every session. A pending or disabled account cannot create or continue a session.

## Account Interface

The bottom-rail profile control will open a global Account page during the post-membership desktop UI
pass. That page will show the signed-in display name and email and expose the existing Change Email
flow as an explicit account action. It remains separate from Workspace Settings because membership,
role, invitation, and ownership controls are scoped to one workspace rather than the global identity.

## Temporary Server Administration

The deployment operator may create a verified named account interactively for recovery or controlled
bootstrap operation:

```powershell
$env:VIRTUAL_ENV = (Resolve-Path "..\.venv").Path
$env:PYTHONPATH = (Resolve-Path "src").Path
uv run --active --no-sync python -m authentication.account_admin create
```

The `create` command prompts for display name, email, and password; the password is requested twice
without echo and is never accepted as a command argument. Account tooling can also run
`create-owner`, `reset-password`, `disable`, and
`enable` with an interactively entered email. Creating the account does not create a workspace or
membership.

## Notification Email Boundary

Login addresses belong to the people using Leave Planner. Merydio does not create a mailbox such as
`admin@merydio.co.uk` for every administrator.

Transactional mail will later be sent from a dedicated authenticated sender such as

`notifications@merydio.co.uk`. That address need not receive mail. If human replies are required, a
separately configured and monitored support inbox can be supplied as Reply-To. In-app request
state remains authoritative, while transactional messages notify each Owner or Admin at their
registered address.

## Calculation Boundary

Authentication wraps existing workspace authorization and does not modify entitlement, job plans,
public holidays, booking deductions, applied values, Decimal handling, or balance derivation.
