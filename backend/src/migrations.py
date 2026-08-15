"""Alembic migration runner used by startup and tests."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from resources import alembic_configuration, migration_directory


def alembic_config(database_path: Path) -> Config:
    config = Config(alembic_configuration())
    config.set_main_option("script_location", str(migration_directory()))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.resolve().as_posix()}",
    )
    return config


def upgrade_database(database_path: Path) -> None:
    """Upgrade a database to the latest schema revision."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(database_path), "head")


def database_requires_upgrade(database_path: Path) -> bool:
    """Return whether an existing database differs from the latest Alembic revision."""

    if not database_path.is_file():
        return False

    config = alembic_config(database_path)
    script = ScriptDirectory.from_config(config)
    expected_revision = script.get_current_head()

    try:
        with sqlite3.connect(database_path) as connection:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.DatabaseError:
        return True

    return row is None or row[0] != expected_revision
