"""Runtime configuration and API error tests."""

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

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
    settings = Settings(
        environment="production",
        data_dir=tmp_path,
        database_url=SecretStr(
            "postgresql+psycopg://leave_planner:secret@database/leave_planner"
        ),
        port=8123,
    )

    assert settings.environment == "production"
    assert settings.resolved_database_url.get_backend_name() == "postgresql"
    assert settings.sqlite_database_path is None
    assert settings.port == 8123
    assert "secret" not in repr(settings)


@pytest.mark.sqlite_only
def test_development_defaults_to_a_local_sqlite_database(tmp_path: Path) -> None:
    settings = Settings(environment="development", data_dir=tmp_path)

    assert settings.uses_sqlite
    assert settings.database_path == tmp_path / "leave-planner.sqlite3"


def test_production_rejects_sqlite_and_unsupported_database_drivers(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(
            environment="production",
            database_url=SecretStr(
                f"sqlite+pysqlite:///{(tmp_path / 'test.sqlite3').as_posix()}"
            ),
        )

    with pytest.raises(ValidationError, match=r"sqlite\+pysqlite or postgresql\+psycopg"):
        Settings(
            environment="test",
            database_url=SecretStr("mysql+pymysql://database/example"),
        )


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
