# PostgreSQL Application Foundation

## Runtime boundary

Leave Planner accepts one SQLAlchemy database URL. Development and focused tests may omit it and
continue to use the local SQLite file. A hosted production process must supply a
`postgresql+psycopg` URL; production startup rejects SQLite and ambiguous or unsupported drivers.

The password is held by the settings layer as a secret value. Do not commit a populated `.env`
file, paste a real URL into logs, or put credentials in `Implementation.md`. The checked-in
`backend/.env.example` contains placeholders only.

Example hosted values:

```text
LEAVE_PLANNER_ENVIRONMENT=production
LEAVE_PLANNER_DATABASE_URL=postgresql+psycopg://leave_planner:<password>@database:5432/leave_planner
```

`database` is the future Compose service name. A local or temporary test server can use its actual
host and port instead.

## Startup flow

FastAPI resolves and validates the URL, runs Alembic against that URL, creates a backend-aware
SQLAlchemy engine, and then creates the shared session factory used by the existing repositories.
Models continue to store leave quantities as fixed-precision numeric values, while API contracts
continue to serialize `Decimal` quantities as strings. No calculation rule changes at this layer.

SQLite connection PRAGMAs are installed only for SQLite engines. The SQLite file-copy backup and
restore API is also mounted only for SQLite. PostgreSQL backup and restore will use database dumps
and is deliberately owned by Phase 6 task 10; copying PostgreSQL data files while the server is
running is not a supported recovery path.

## Verification

The normal backend suite continues to use isolated SQLite databases for fast focused feedback. Set
`LEAVE_PLANNER_TEST_POSTGRES_URL` to an empty disposable PostgreSQL database to run the same API and
migration tests against PostgreSQL. The test fixture drops and recreates that database's `public`
schema before each test, so never point it at a database containing data that must be retained.

From `backend` in PowerShell:

```powershell
$env:VIRTUAL_ENV = (Resolve-Path "..\.venv").Path
$env:LEAVE_PLANNER_TEST_POSTGRES_URL = "postgresql+psycopg://leave_planner:<password>@<host>:<port>/leave_planner_test"
uv run --active --no-sync pytest
```

The focused server proof is:

```powershell
uv run --active --no-sync pytest tests/test_postgresql_runtime.py
```

That proof applies every migration, checks core tables, creates and reads a consultant through the
HTTP API, and confirms the SQLite recovery surface is absent.
