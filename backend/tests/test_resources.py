"""Resource-path tests for the repository application layout."""

from pathlib import Path

import resources


def test_source_resources_resolve_from_the_repository() -> None:
    """Development runs read the frontend and Alembic files from the repository."""

    backend_root = Path(resources.__file__).resolve().parents[1]
    project_root = backend_root.parent

    assert resources.resource_root() == backend_root
    assert resources.frontend_distribution() == project_root / "frontend" / "dist"
    assert resources.policy_reference_directory() == project_root / "docs" / "reference"
    assert resources.alembic_configuration() == backend_root / "alembic.ini"
    assert resources.migration_directory() == backend_root / "migrations"
