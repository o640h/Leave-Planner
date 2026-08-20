"""Database-independent Alembic migration runner used by startup and tests."""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import URL
from sqlalchemy.exc import DBAPIError

from database import create_database_engine, database_url, sqlite_url
from resources import alembic_configuration, migration_directory

DatabaseLocation = str | URL | Path


class DatabaseUpgradeRequired(RuntimeError):
    """Raised when production starts against a schema that was not explicitly migrated."""


def resolved_url(location: DatabaseLocation) -> URL:
    return (
        sqlite_url(location.expanduser().resolve())
        if isinstance(location, Path)
        else database_url(location)
    )


def alembic_config(location: DatabaseLocation) -> Config:
    url = resolved_url(location)
    config = Config(alembic_configuration())
    config.set_main_option("script_location", str(migration_directory()))
    config.set_main_option(
        "sqlalchemy.url",
        url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return config


def upgrade_database(location: DatabaseLocation) -> None:
    """Upgrade a database to the latest schema revision."""

    url = resolved_url(location)
    database_path = url.database
    if (
        url.get_backend_name() == "sqlite"
        and database_path is not None
        and database_path != ":memory:"
    ):
        Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(url), "head")


def database_requires_upgrade(location: DatabaseLocation) -> bool:
    """Return whether a reachable database differs from the latest Alembic revision."""

    url = resolved_url(location)
    database_path = url.database
    if (
        url.get_backend_name() == "sqlite"
        and database_path is not None
        and database_path != ":memory:"
        and not Path(database_path).is_file()
    ):
        return False

    config = alembic_config(url)
    script = ScriptDirectory.from_config(config)
    expected_revision = script.get_current_head()
    engine = create_database_engine(url)

    try:
        with engine.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
    except DBAPIError:
        if url.get_backend_name() == "sqlite":
            return True
        raise
    finally:
        engine.dispose()

    return current_revision != expected_revision


def require_database_current(location: DatabaseLocation) -> None:
    """Fail clearly when the configured schema is not at the current revision."""

    if database_requires_upgrade(location):
        raise DatabaseUpgradeRequired(
            "The database schema is not current. Run the explicit migration command before "
            "starting the production application."
        )


def main() -> None:
    """Run or verify the configured database migration as a server-owner operation."""

    from settings import Settings

    parser = argparse.ArgumentParser(description="Manage the Leave Planner database schema")
    parser.add_argument("operation", choices=("upgrade", "check"))
    operation = parser.parse_args().operation
    runtime = Settings()

    if operation == "upgrade":
        upgrade_database(runtime.resolved_database_url)
        require_database_current(runtime.resolved_database_url)
        print("Database schema upgraded successfully.")
    else:
        require_database_current(runtime.resolved_database_url)
        print("Database schema is current.")


if __name__ == "__main__":
    main()
