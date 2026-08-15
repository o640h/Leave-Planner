"""Resolve application resources in source and packaged environments."""

import sys
from pathlib import Path


def is_packaged() -> bool:
    """Return whether Leave Planner is running from a PyInstaller bundle."""

    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Return the directory containing bundled read-only resources."""

    current_file = Path(__file__).resolve()

    if is_packaged():
        return current_file.parent

    return current_file.parents[1]


def frontend_distribution() -> Path:
    """Return the compiled React frontend directory."""

    root = resource_root()

    if is_packaged():
        return root / "frontend" / "dist"

    return root.parent / "frontend" / "dist"


def alembic_configuration() -> Path:
    """Return the Alembic configuration file."""

    return resource_root() / "alembic.ini"


def migration_directory() -> Path:
    """Return the bundled Alembic migration directory."""

    return resource_root() / "migrations"
