"""Runtime configuration and API error tests."""

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

import main as main_module
from errors import ApiError
from logging_config import JsonFormatter
from main import create_app
from migrations import DatabaseUpgradeRequired
from settings import Settings, default_data_directory


def test_windows_data_directory_uses_local_app_data(tmp_path: Path) -> None:
    result = default_data_directory(
        {"LOCALAPPDATA": str(tmp_path)}, platform="win32", home=Path("C:/fallback")
    )

    assert result == tmp_path / "LeavePlanner"


def test_settings_support_production_overrides(tmp_path: Path) -> None:
    settings = Settings(
        environment="production",
        public_origin="https://leaveplanner.synology.me",
        data_dir=tmp_path,
        database_url=SecretStr("postgresql+psycopg://leave_planner:secret@database/leave_planner"),
        port=8123,
        email_provider="resend",
        resend_api_key_file=Path(__file__),
    )

    assert settings.environment == "production"
    assert settings.resolved_database_url.get_backend_name() == "postgresql"
    assert settings.sqlite_database_path is None
    assert settings.port == 8123
    assert "secret" not in repr(settings)


def test_settings_read_database_url_from_secret_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "database-url.txt"
    secret_file.write_text(
        "postgresql+psycopg://leave_planner:secret@database/leave_planner\n",
        encoding="utf-8",
    )

    settings = Settings(
        environment="production",
        public_origin="https://leaveplanner.synology.me",
        database_url_file=secret_file,
        email_provider="resend",
        resend_api_key_file=Path(__file__),
    )

    assert settings.resolved_database_url.username == "leave_planner"
    assert settings.resolved_database_url.password == "secret"
    assert "secret" not in repr(settings)


def test_settings_reject_ambiguous_database_secrets(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="either database_url or database_url_file"):
        Settings(
            environment="production",
            public_origin="https://leaveplanner.synology.me",
            database_url=SecretStr(
                "postgresql+psycopg://leave_planner:secret@database/leave_planner"
            ),
            database_url_file=tmp_path / "database-url.txt",
        )


@pytest.mark.sqlite_only
def test_development_defaults_to_a_local_sqlite_database(tmp_path: Path) -> None:
    settings = Settings(environment="development", data_dir=tmp_path)

    assert settings.uses_sqlite
    assert settings.database_path == tmp_path / "leave-planner.sqlite3"


def test_production_rejects_sqlite_and_unsupported_database_drivers(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(
            environment="production",
            public_origin="https://leaveplanner.synology.me",
            database_url=SecretStr(f"sqlite+pysqlite:///{(tmp_path / 'test.sqlite3').as_posix()}"),
        )


def test_production_refuses_to_start_before_explicit_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        environment="production",
        public_origin="https://leaveplanner.synology.me",
        database_url=SecretStr("postgresql+psycopg://leave_planner:secret@database/leave_planner"),
        email_provider="resend",
        resend_api_key_file=Path(__file__),
    )

    def reject_unmigrated_database(_location: object) -> None:
        raise DatabaseUpgradeRequired("Run the explicit migration command")

    monkeypatch.setattr(main_module, "require_database_current", reject_unmigrated_database)
    app = create_app(settings=settings)

    with (
        pytest.raises(DatabaseUpgradeRequired, match="explicit migration command"),
        TestClient(app),
    ):
        pass

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
