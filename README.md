# Leave Planner

Leave Planner is a consultant annual-leave planning application. It replaces the one-workbook-per-consultant workflow with consultant records, job plans, entitlement calculations, public holidays, leave booking, balances, audit history, and recovery tools.

The completed local release uses React and TypeScript, FastAPI, and SQLite. The current development phase is converting that workflow into an authenticated browser application backed by PostgreSQL and deployed as containers on a Synology NAS. Windows packaging and desktop runtime integrations have been retired.

Policy documents and the reference workbook are retained in [`docs/reference`](docs/reference); calculation and maintenance notes are in [`docs/explanations`](docs/explanations).

## Browser Development

Use two PowerShell terminals. Start the FastAPI backend in the first:

```powershell
Set-Location "C:\Projects\Leave Planner\backend"
$env:VIRTUAL_ENV = (Resolve-Path "..\.venv").Path
$env:PYTHONPATH = (Resolve-Path "src").Path
uv sync --active --locked --group dev
uv run --active --no-sync uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Phase 7 uses named email accounts. The first Owner and blank workspace are created by the later
owner-onboarding task; the shared Admin account has been retired. The identity model and temporary
server-side account command are documented in
[`docs/explanations/email-identity-authentication.md`](docs/explanations/email-identity-authentication.md).
Local password recovery does not need a real mailbox: development captures messages in a safe
outbox. The complete test walkthrough and production Resend boundary are documented in
[`docs/explanations/transactional-email-and-account-recovery.md`](docs/explanations/transactional-email-and-account-recovery.md).

Start Vite in the second:

```powershell
Set-Location "C:\Projects\Leave Planner\frontend"
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to FastAPI at
`http://127.0.0.1:8000`. After dependencies are installed, later development runs need only the
`uv run ... uvicorn` and `npm.cmd run dev` commands.

Local browser development continues to use an isolated SQLite file by default. Hosted production
requires a `postgresql+psycopg` database URL. See
[`docs/explanations/postgresql-foundation.md`](docs/explanations/postgresql-foundation.md) and
[`backend/.env.example`](backend/.env.example) for the configuration and disposable PostgreSQL test
command. The one-time transfer of an accepted local database is documented in
[`docs/explanations/sqlite-to-postgresql-import.md`](docs/explanations/sqlite-to-postgresql-import.md).

## Container Deployment

The production deployment is defined by [`Dockerfile`](Dockerfile) and
[`deploy/compose.yml`](deploy/compose.yml). It builds the React assets into the lean FastAPI image,
runs PostgreSQL on an internal-only container network, and requires a separate successful migration
service before the application starts. Generate the five database secret files, add the ignored
Resend API-key file described in the transactional-email guide, and validate the configuration from
the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\NewDeploymentSecrets.ps1"
docker compose --file deploy/compose.yml config --quiet
```

Do not regenerate secrets after the persistent PostgreSQL volume is initialized. The initial release,
Admin provisioning, restart/recreation checks, upgrades, resource limits, and Synology handoff are
documented in
[`docs/explanations/container-deployment.md`](docs/explanations/container-deployment.md).
