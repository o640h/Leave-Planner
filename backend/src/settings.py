"""Typed application settings and local path resolution."""

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from database import database_url, sqlite_url
from resources import frontend_distribution

Environment = Literal["development", "production", "test"]


def default_data_directory(
    environment: Mapping[str, str] | None = None,
    *,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve an OS-appropriate directory for durable, user-scoped application data."""
    values = os.environ if environment is None else environment
    current_platform = sys.platform if platform is None else platform
    user_home = Path.home() if home is None else home

    if current_platform == "win32":
        base = Path(values.get("LOCALAPPDATA", user_home / "AppData" / "Local"))
        return base / "LeavePlanner"

    xdg_data_home = values.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else user_home / ".local" / "share"
    return base / "leave-planner"


class Settings(BaseSettings):
    """Environment-controlled settings for development, tests, and hosted runtime."""

    model_config = SettingsConfigDict(
        env_prefix="LEAVE_PLANNER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Leave Planner"
    environment: Environment = "development"
    host: Literal["127.0.0.1", "localhost"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    data_dir: Path | None = None
    database_url: SecretStr | None = None
    database_url_file: Path | None = None
    frontend_dist: Path | None = None
    authentication_required: bool = True
    session_lifetime_hours: int = Field(default=12, ge=1, le=168)

    @model_validator(mode="after")
    def validate_database_configuration(self) -> Settings:
        if self.database_url is not None and self.database_url_file is not None:
            raise ValueError("Configure either database_url or database_url_file, not both")
        url = self.resolved_database_url
        if self.environment == "production" and url.get_backend_name() != "postgresql":
            raise ValueError("Production requires a postgresql+psycopg database URL")
        if self.environment == "production" and not self.authentication_required:
            raise ValueError("Production requires authentication")
        return self

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir.expanduser().resolve() if self.data_dir else default_data_directory()

    @property
    def database_path(self) -> Path:
        path = self.sqlite_database_path
        if path is None:
            raise RuntimeError("The configured database is not a file-backed SQLite database")
        return path

    @property
    def resolved_database_url(self) -> URL:
        if self.database_url is not None:
            return database_url(self.database_url.get_secret_value())
        if self.database_url_file is not None:
            secret_path = self.database_url_file.expanduser().resolve()
            try:
                value = secret_path.read_text(encoding="utf-8").strip()
            except OSError as error:
                raise ValueError("The database URL secret file could not be read") from error
            if not value:
                raise ValueError("The database URL secret file is empty")
            return database_url(value)
        return sqlite_url(self.resolved_data_dir / "leave-planner.sqlite3")

    @property
    def sqlite_database_path(self) -> Path | None:
        url = self.resolved_database_url
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            return None
        return Path(url.database).expanduser().resolve()

    @property
    def uses_sqlite(self) -> bool:
        return self.resolved_database_url.get_backend_name() == "sqlite"

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_name(self) -> str:
        return "__Host-id" if self.secure_cookies else "leave_planner_id"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-csrf" if self.secure_cookies else "leave_planner_csrf"

    @property
    def backup_directory(self) -> Path:
        return self.resolved_data_dir / "backups"

    @property
    def resolved_frontend_dist(self) -> Path:
        if self.frontend_dist:
            return self.frontend_dist.expanduser().resolve()

        return frontend_distribution()
