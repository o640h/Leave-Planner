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
uv run --active --no-sync python -m authentication.admin create
uv run --active --no-sync uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Run the `create` command once for a new development database. It securely prompts twice for the
password and creates the fixed `Admin` account; it never accepts or prints the password on the command
line. Account reset, disable, and enable commands are documented in
[`docs/explanations/shared-admin-authentication.md`](docs/explanations/shared-admin-authentication.md).

Start Vite in the second:

```powershell
Set-Location "C:\Projects\Leave Planner\frontend"
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to FastAPI at
`http://127.0.0.1:8000`. After dependencies are installed, later development runs need only the
`uv run ... uvicorn` and `npm.cmd run dev` commands. Do not repeat the `create` command after the
account exists.

Local browser development continues to use an isolated SQLite file by default. Hosted production
requires a `postgresql+psycopg` database URL. See
[`docs/explanations/postgresql-foundation.md`](docs/explanations/postgresql-foundation.md) and
[`backend/.env.example`](backend/.env.example) for the configuration and disposable PostgreSQL test
command. The one-time transfer of an accepted local database is documented in
[`docs/explanations/sqlite-to-postgresql-import.md`](docs/explanations/sqlite-to-postgresql-import.md).
