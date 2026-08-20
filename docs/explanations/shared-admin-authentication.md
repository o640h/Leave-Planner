# Shared Admin Authentication

## Operator outcome

Leave Planner has one password-only account named `Admin`. The browser checks the current session
before loading consultant data and shows the application only after successful authentication. There
is no username field, registration, email identity, invitation, MFA, or browser password recovery.

The account is deliberately shared for this development stage. Authentication events can identify
`Admin`, but cannot identify which person knew the shared password. Individual accounts and domain
audit actors remain part of the workspace-authorization task.

## Server administration

Run account commands from `backend` with the project root environment active. Every password prompt
uses `getpass`, asks for confirmation, and does not echo or accept the password as an argument.

```powershell
$env:VIRTUAL_ENV = (Resolve-Path "..\.venv").Path
$env:PYTHONPATH = (Resolve-Path "src").Path
uv run --active --no-sync python -m authentication.admin create
uv run --active --no-sync python -m authentication.admin reset-password
uv run --active --no-sync python -m authentication.admin disable
uv run --active --no-sync python -m authentication.admin enable
```

The enforced development-stage minimum is 10 characters, as accepted by the operator. There are no
composition rules. A password reset increments the password version and revokes every existing
session. Disabling the account also revokes every session. The minimum and chosen password strength
must be reviewed before external exposure because this shared account has no second factor.

The command uses the same `LEAVE_PLANNER_ENVIRONMENT` and `LEAVE_PLANNER_DATABASE_URL` values as the
server. Running it without those hosted values manages the normal local-development SQLite database.

## Request flow

`POST /api/auth/login` verifies the password with Argon2id and creates a 12-hour server-side session.
The browser receives an opaque session cookie and a separate CSRF cookie. Only SHA-256 hashes of both
tokens are stored. Authentication responses are marked `Cache-Control: no-store`.

Production cookies use the `__Host-` prefix, `Secure`, `SameSite=Strict`, and `Path=/`; the session
cookie is also `HttpOnly`. Local HTTP development uses separate non-Secure names so browsers can test
the flow at `localhost`. Tokens are never put in local or session storage.

Every existing application router has one central authentication dependency. State-changing
requests additionally require the readable CSRF value in `X-CSRF-Token`, a matching server-side
hash, and a same-origin `Origin` header when the client sends one. Health, login, and current-session
status remain public. Logout requires an authenticated, CSRF-validated request and revokes the
server-side record before clearing cookies.

Five consecutive failed attempts lock `Admin` for 15 minutes. The failure count and dated lock are
stored in the database, so an application restart cannot bypass them and concurrent attempts are
serialized through the Admin row. A successful login, password reset, account enable/disable, or
completed lockout clears the failure count. Attempts made during the lockout still perform the
expensive password verification and return the same temporary-unavailability response.

While the account is locked, the sign-in screen shows a minute-and-second countdown using the
server-provided retry duration and disables further submissions until it expires. This makes the
shared, deployment-wide lock visible and avoids extending load with repeated login requests.

## Persistence and audit

- `users` stores the stable Admin identity, Argon2id hash, enabled state, password version, and dated
  lifecycle fields.
- `user_sessions` stores token hashes, password version, expiry, last-seen time, and revocation.
- `security_events` records account creation, login outcomes, logout, reset, disable, and enable
  without passwords, tokens, hashes, request bodies, or raw network addresses.

Focused calculation/API tests opt out explicitly through test-only settings. Production settings
reject that bypass. Authentication integration tests run with protection enabled and prove direct API
denial, CSRF enforcement, origin rejection, token hashing, expiry, revocation, and secure-cookie
attributes.
