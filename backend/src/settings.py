"""Typed application settings and local path resolution."""

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    """Environment-controlled settings for development, tests, and packaged runtime."""

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
    frontend_dist: Path | None = None

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir.expanduser().resolve() if self.data_dir else default_data_directory()

    @property
    def database_path(self) -> Path:
        return self.resolved_data_dir / "leave-planner.sqlite3"

    @property
    def backup_directory(self) -> Path:
        return self.resolved_data_dir / "backups"

    @property
    def resolved_frontend_dist(self) -> Path:
        if self.frontend_dist:
            return self.frontend_dist.expanduser().resolve()

        return frontend_distribution()
