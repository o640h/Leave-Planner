# Backend

The backend is a flat-module Python 3.11 `uv` project. Application modules live directly in `src/`; tests live in `tests/`; Alembic configuration and migrations live at this directory's root.

Use the project-root `.venv`. From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uv sync --project backend --active
uv run --active --directory backend uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 8000
uv run --active --directory backend ruff check .
uv run --active --directory backend mypy
uv run --active --directory backend pytest
```

Copy `backend/.env.example` to `backend/.env` for local overrides. Production remains loopback-only and durable data resolves to `%LOCALAPPDATA%\LeavePlanner` by default.