# Leave Planner

Leave Planner is a focused annual-leave planning and calculation application for a locally managed team of consultants.

The product is a single-operator Windows application with a React/TypeScript frontend, FastAPI backend, SQLite storage, effective-dated job plans, DCC/SPA/Other activity tracking, leave lifecycle states, policy-aware warnings, team planning, audit history, backups, and exports.

## Project status

The engineering foundation, quality gates, runtime configuration, database migrations, and backup service are operational.

## Local setup

Prerequisites: Python 3.11, `uv`, Node.js, and npm.

Create the Python environment yourself:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
uv sync --project backend --active
```

Install frontend dependencies:

```powershell
npm.cmd install --prefix frontend
```

Run the backend and frontend in separate terminals:

```powershell
uv run --active --directory backend uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

```powershell
npm.cmd run dev --prefix frontend
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`.

## Verification

```powershell
uv run --active --directory backend ruff check .
uv run --active --directory backend mypy
uv run --active --directory backend pytest
npm.cmd run lint --prefix frontend
npm.cmd run format:check --prefix frontend
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
```

After the frontend build, FastAPI serves `frontend/dist` at `http://127.0.0.1:8000/`.