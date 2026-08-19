"""Database-independent Alembic migration runner used by startup and tests."""

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
    if url.get_backend_name() == "sqlite" and url.database not in {None, ":memory:"}:
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(url), "head")


def database_requires_upgrade(location: DatabaseLocation) -> bool:
    """Return whether a reachable database differs from the latest Alembic revision."""

    url = resolved_url(location)
    if (
        url.get_backend_name() == "sqlite"
        and url.database not in {None, ":memory:"}
        and not Path(url.database).is_file()
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
