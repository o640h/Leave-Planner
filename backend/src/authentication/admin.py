"""Interactive server-owner administration for the fixed Admin account."""

import argparse
from getpass import getpass

from database import create_database_engine, create_session_factory, session_scope
from migrations import require_database_current, upgrade_database
from recovery import create_startup_backups
from settings import Settings

from .service import create_admin, reset_admin_password, set_admin_enabled


def confirmed_password() -> str:
    password = getpass("New Admin password: ")
    confirmation = getpass("Confirm Admin password: ")
    if password != confirmation:
        raise ValueError("The passwords did not match")
    return password


def run(operation: str, settings: Settings | None = None) -> None:
    runtime = settings or Settings()
    create_startup_backups(runtime)
    if runtime.environment == "production":
        require_database_current(runtime.resolved_database_url)
    else:
        upgrade_database(runtime.resolved_database_url)
    engine = create_database_engine(runtime.resolved_database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            if operation == "create":
                create_admin(session, confirmed_password())
            elif operation == "reset-password":
                reset_admin_password(session, confirmed_password())
            elif operation == "disable":
                set_admin_enabled(session, enabled=False)
            elif operation == "enable":
                set_admin_enabled(session, enabled=True)
            else:
                raise ValueError(f"Unsupported operation: {operation}")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the Leave Planner Admin account")
    parser.add_argument("operation", choices=("create", "reset-password", "disable", "enable"))
    arguments = parser.parse_args()
    try:
        run(arguments.operation)
    except ValueError as error:
        parser.error(str(error))
    print(f"Admin operation completed: {arguments.operation}")


if __name__ == "__main__":
    main()
