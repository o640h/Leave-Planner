"""Backend-neutral SQL assertions used by API persistence tests."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sqlalchemy import text

from database import create_database_engine
from settings import Settings


def rows(
    data_dir: Path,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> list[tuple[Any, ...]]:
    settings = Settings(environment="test", data_dir=data_dir)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(statement), parameters or {})]
    finally:
        engine.dispose()


def row(
    data_dir: Path,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> tuple[Any, ...] | None:
    records = rows(data_dir, statement, parameters)
    return records[0] if records else None
