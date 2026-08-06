"""Runtime configuration and API error tests."""

import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from errors import ApiError
from logging_config import JsonFormatter
from main import create_app
from settings import Settings, default_data_directory


def test_windows_data_directory_uses_local_app_data(tmp_path: Path) -> None:
    result = default_data_directory(
        {"LOCALAPPDATA": str(tmp_path)}, platform="win32", home=Path("C:/fallback")
    )

    assert result == tmp_path / "LeavePlanner"


def test_settings_support_production_overrides(tmp_path: Path) -> None:
    settings = Settings(environment="production", data_dir=tmp_path, port=8123)

    assert settings.environment == "production"
    assert settings.database_path == tmp_path / "leave-planner.sqlite3"
    assert settings.port == 8123


def test_api_errors_use_stable_envelope(tmp_path: Path) -> None:
    app = create_app(frontend_dist=tmp_path / "missing")

    @app.get("/api/fail")
    async def fail() -> None:
        raise ApiError(status_code=409, code="example_conflict", message="Example conflict")

    response = TestClient(app).get("/api/fail")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "example_conflict",
            "message": "Example conflict",
            "details": None,
        }
    }


def test_json_formatter_emits_structured_record() -> None:
    record = logging.LogRecord("leave-planner", logging.INFO, __file__, 1, "ready", (), None)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "leave-planner"
    assert payload["message"] == "ready"
    assert "timestamp" in payload
