# Backend

The backend is a flat-module Python 3.11 `uv` project. Application modules live directly in `src/`; tests live in `tests/`; Alembic configuration and migrations live at this directory's root.

Use the project-root `.venv`. From the repository root, activate it and enter the backend once:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location backend
uv sync --active
python -m uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 8000
ruff check .
mypy
pytest
```

`uv sync` can be short because the current directory identifies the project. Bare `uv run` cannot
start the application by itself because `uv` still needs a command to run; once the environment is
active, invoking `python`, `pytest`, `ruff`, and `mypy` directly is clearer.

Copy `backend/.env.example` to `backend/.env` for local overrides. Production remains loopback-only and durable data resolves to `%LOCALAPPDATA%\LeavePlanner` by default.
