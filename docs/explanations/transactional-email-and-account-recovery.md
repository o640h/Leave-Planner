# Transactional Email and Account Recovery

## Operator-visible behaviour

Leave Planner sends account messages through one small delivery boundary. Development uses an
in-memory outbox; production uses Resend's HTTPS API. The application remains the authority for
accounts, sessions, workspaces, and every action token. Resend receives only the destination address,
generic account-message content, and delivery metadata needed to send that message.

The implemented flows are:

- account creation can issue a verification message and activate the pending account through its
  link; this is deliberately not a separate action on the sign-in screen;
- an active account can request a password reset without revealing whether the address exists;
- a reset changes the password and revokes every existing session and unused account-action token;
- a signed-in account can confirm its password, request a change to a new address, confirm the new
  address, and receive a notification at the old address; confirmation revokes every session;
- invitation tokens use the same seven-day, single-use storage model, ready for the membership slice,
  but invitation delivery and acceptance are not exposed before that workflow exists.

Verification and email-change links last 24 hours. Password-reset links last one hour. A newly issued
link of the same type revokes the older unused link. Responses to public request endpoints are generic,
and the shared request boundary applies a separate per-client limit to account-action endpoints.

## Data and call flow

`authentication/account_router.py` validates the API input and coordinates each flow. It asks
`authentication/account_actions.py` to generate a cryptographically random token, stores only its
SHA-256 hash in `account_action_tokens`, commits the pending action, and builds the browser link from
the configured public origin. `authentication/email_delivery.py` then hands a plain-text message to
either `DevelopmentOutbox` or `ResendEmailSender`.

Each delivery creates an `email_delivery_attempts` row with a masked recipient hint, purpose,
idempotency key, result, and provider message ID or a small failure code. Raw tokens, passwords, full
recipient addresses, and message bodies are not copied into database logs or security-event details.
If delivery fails, the public response stays generic and existing accounts and workspaces are not
changed. Requesting another message creates one replacement token and revokes the previous one.

The browser reads `action` and `token` from a root-page link and presents the matching verification,
password-reset, or email-change confirmation screen. Passwords are still hashed with the existing
Argon2id settings. Email changes require the current password and record recent re-authentication
before a confirmation message is sent.

## Local testing without real email

The default development configuration uses `development_outbox`. It never sends a network message,
so use any syntactically valid address such as `operator@example.org`; it does not need to be your
real address.

To create the first verified Owner account and its blank workspace, run this in a PowerShell terminal:

```powershell
Set-Location "C:\Projects\Leave Planner\backend"
$env:PYTHONPATH = (Resolve-Path "src").Path
..\.venv\Scripts\python.exe -m authentication.account_admin create-owner
```

Enter the email, display name, password of at least eight characters, and workspace name at the
prompts. Sign in at `http://localhost:5173`; the single Owner workspace is selected automatically.

Use **Forgot Password** to test recovery. After requesting the link, open this development-only URL:

```text
http://localhost:5173/api/auth/development/email-outbox
```

Copy the complete link from the latest message's `text` value into the browser. The outbox is held in
memory and clears whenever FastAPI restarts. In particular, `--reload` clears it after a source-file
change. If that happens, request another message after the restart or run without `--reload` while
testing account links. The endpoint returns `404` in production and is never an alternative
production mailbox.

Email verification is not a standalone sign-in action. The token-confirmation path is retained for
the account-creation workflow, which will send the initial message and provide any necessary resend
action within that workflow.

For narrowly scoped local diagnosis, FastAPI can still be started with authentication disabled:

```powershell
$env:LEAVE_PLANNER_AUTHENTICATION_REQUIRED = "false"
..\.venv\Scripts\uvicorn.exe main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Remove that environment variable before testing sign-in. This bypass is rejected in production and
must never be added to the NAS configuration.

## Production delivery checklist

Production application startup is fail-closed: it requires `LEAVE_PLANNER_EMAIL_PROVIDER=resend` and
a readable `LEAVE_PLANNER_RESEND_API_KEY_FILE`. Compose mounts the ignored NAS secret
`deploy/secrets/resend_api_key.txt` at `/run/secrets/resend_api_key`. Create that file manually from a
restricted Resend API key; the database-secret generator cannot manufacture it.

The selected From identity is `Leave Planner <notifications@merydio.co.uk>`. Resend does not require
that address to be created as a mailbox after the domain is verified, although a monitored Reply-To
address can be configured separately. Before deployment:

1. add and verify `merydio.co.uk` in Resend;
2. publish the exact SPF and DKIM records Resend supplies without replacing records used by other
   legitimate mail services;
3. assess the domain's existing mail senders, publish a DMARC monitoring policy first if one is not
   already present, inspect reports, and strengthen enforcement only when legitimate sources align;
4. send verification and reset messages to controlled test addresses and confirm delivery, link
   origin, expiry, single use, resend invalidation, and old-address notification;
5. confirm application logs and security-event details contain no raw link or complete address.

DNS values must come from the live Resend domain page. They are deliberately not hard-coded in this
repository. Production verification remains an operational checkpoint until those records and the
NAS secret have been configured and tested.

### Files and local Resend test

The repository already contains the production wiring:

- `deploy/compose.yml` selects Resend, sets the From identity, and mounts the API-key secret;
- `deploy/.env` supplies the deployed public origin and version from `.env.example`;
- `deploy/secrets/resend_api_key.txt` is the ignored file that you create and copy to the NAS;
- `backend/src/settings.py` reads the provider, sender, optional Reply-To, and secret-file path.

To try real delivery from the local backend, create the ignored
`deploy/secrets/resend_api_key.txt` containing only the API key. Then create the ignored
`backend/.env` with:

```dotenv
LEAVE_PLANNER_EMAIL_PROVIDER=resend
LEAVE_PLANNER_EMAIL_FROM="Leave Planner <notifications@merydio.co.uk>"
LEAVE_PLANNER_RESEND_API_KEY_FILE=../deploy/secrets/resend_api_key.txt
LEAVE_PLANNER_PUBLIC_ORIGIN=http://localhost:5173
```

Start FastAPI from `backend` so that the relative secret path resolves as shown. Remove or rename
`backend/.env` to return to the development outbox. Never put the API-key value directly in either
`.env` file, Compose YAML, a command line, or source code.
