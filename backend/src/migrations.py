"""Alembic migration runner used by startup and tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config


def alembic_config(database_path: Path) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.resolve().as_posix()}")
    return config


def upgrade_database(database_path: Path) -> None:
    """Upgrade a database to the latest schema revision."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(database_path), "head")
