"""Typed application settings and local path resolution."""

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from database import database_url, sqlite_url
from resources import frontend_distribution

Environment = Literal["development", "production", "test"]
EmailProvider = Literal["development_outbox", "resend"]
RegistrationMode = Literal["closed", "invitation_only", "open"]
TrustedProxyMode = Literal["none", "cloudflare_tunnel"]


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
    public_origin: str | None = None
    max_request_bytes: int = Field(default=1_048_576, ge=1, le=10_485_760)
    request_rate_limit: int = Field(default=240, ge=1, le=10_000)
    login_rate_limit: int = Field(default=10, ge=1, le=1_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    account_action_rate_limit: int = Field(default=5, ge=1, le=100)
    sensitive_action_rate_limit: int = Field(default=30, ge=1, le=1_000)
    rate_limit_max_keys: int = Field(default=10_000, ge=100, le=100_000)
    trusted_proxy_mode: TrustedProxyMode = "none"
    websocket_connection_rate_limit: int = Field(default=12, ge=1, le=100)
    websocket_connections_per_account: int = Field(default=5, ge=1, le=20)
    websocket_message_rate_limit: int = Field(default=40, ge=20, le=500)
    websocket_revalidation_seconds: int = Field(default=30, ge=5, le=300)
    registration_mode: RegistrationMode = "open"
    owned_workspace_limit: int = Field(default=3, ge=1, le=20)
    email_provider: EmailProvider = "development_outbox"
    email_from: str = "Leave Planner <notifications@merydio.co.uk>"
    email_reply_to: str | None = None
    resend_api_key_file: Path | None = None

    @model_validator(mode="after")
    def validate_database_configuration(self) -> Self:
        if self.database_url is not None and self.database_url_file is not None:
            raise ValueError("Configure either database_url or database_url_file, not both")
        url = self.resolved_database_url
        if self.environment == "production" and url.get_backend_name() != "postgresql":
            raise ValueError("Production requires a postgresql+psycopg database URL")
        if self.environment == "production" and not self.authentication_required:
            raise ValueError("Production requires authentication")
        if self.environment != "production" and self.trusted_proxy_mode != "none":
            raise ValueError("Trusted proxy mode is only available in production")
        if self.email_provider == "resend" and self.resend_api_key_file is None:
            raise ValueError("The Resend provider requires resend_api_key_file")
        if self.public_origin is not None:
            parsed = urlsplit(self.public_origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("public_origin must be an HTTP(S) origin without a path")
            if self.environment == "production" and parsed.scheme != "https":
                raise ValueError("Production public_origin must use HTTPS")
            self.public_origin = self.public_origin.rstrip("/")
        return self

    @property
    def resend_api_key(self) -> str:
        if self.resend_api_key_file is None:
            raise RuntimeError("The Resend API key file is not configured")
        path = self.resend_api_key_file.expanduser().resolve()
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise RuntimeError("The Resend API key file could not be read") from error
        if not value:
            raise RuntimeError("The Resend API key file is empty")
        return value

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
    def public_host(self) -> str | None:
        if self.public_origin is None:
            return None
        return urlsplit(self.public_origin).hostname

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
