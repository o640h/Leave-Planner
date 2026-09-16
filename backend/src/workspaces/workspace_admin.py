"""Server-owner-only permanent workspace lifecycle operations."""

import argparse

from database import create_database_engine, create_session_factory, session_scope
from migrations import require_database_current
from settings import Settings

from .management import purge_closed_workspace


def run(workspace_id: int, settings: Settings) -> None:
    """Purge one retention-expired workspace after explicit typed confirmation."""

    require_database_current(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            from .models import Workspace

            workspace = session.get(Workspace, workspace_id)
            if workspace is None:
                raise ValueError("Workspace not found")
            print(f"Workspace: {workspace.name}")
            print(f"Status: {workspace.status}")
            print(f"Recovery deadline: {workspace.purge_after}")
            confirmation = input("Type the workspace name exactly: ")
            final_confirmation = input("Type PURGE to permanently delete all workspace data: ")
            if final_confirmation != "PURGE":
                raise ValueError("Permanent deletion was not confirmed")
            removed_name = purge_closed_workspace(
                session,
                workspace_id=workspace_id,
                confirmation_name=confirmation,
            )
        print(f"Workspace permanently deleted: {removed_name}")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run separately authorised workspace lifecycle operations"
    )
    parser.add_argument("operation", choices=("purge-closed",))
    parser.add_argument("workspace_id", type=int)
    arguments = parser.parse_args()
    if arguments.operation == "purge-closed":
        run(arguments.workspace_id, Settings())


if __name__ == "__main__":
    main()
