"""Interactive server-owner administration for named email accounts."""

import argparse
from datetime import UTC, datetime
from getpass import getpass

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import create_database_engine, create_session_factory, session_scope
from migrations import require_database_current, upgrade_database
from recovery import create_startup_backups
from settings import Settings
from workspaces.service import create_initial_owner_workspace

from .models import ACTIVE, DISABLED, User
from .service import (
    account_for_email,
    create_account,
    reset_account_password,
    set_account_state,
)


def entered_email() -> str:
    email = input("Account email: ").strip()
    if not email:
        raise ValueError("Enter an account email")
    return email


def confirmed_password() -> str:
    password = getpass("New account password: ")
    confirmation = getpass("Confirm account password: ")
    if password != confirmation:
        raise ValueError("The passwords did not match")
    return password


def entered_workspace_name() -> str:
    name = input("Workspace name: ").strip()
    if not name:
        raise ValueError("Enter a workspace name")
    return name


def require_account(session: Session, email: str) -> User:
    account = account_for_email(session, email)
    if account is None:
        raise ValueError("The account was not found")
    return account


def require_owner_setup_connection(session: Session, settings: Settings) -> None:
    if settings.environment != "production" or session.get_bind().dialect.name != "postgresql":
        return
    database_role = session.scalar(text("SELECT current_user"))
    if database_role != "leave_planner_migrator":
        raise ValueError(
            "Production first-Owner setup must run through the migrator database connection"
        )


def create_owner(session: Session, settings: Settings) -> None:
    require_owner_setup_connection(session, settings)
    email = entered_email()
    account = account_for_email(session, email, for_update=True)
    if account is None:
        display_name = input("Display name: ").strip()
        password = confirmed_password()
    else:
        display_name = None
        password = getpass("Current account password: ")
    result = create_initial_owner_workspace(
        session,
        email=email,
        password=password,
        workspace_name=entered_workspace_name(),
        display_name=display_name,
    )
    outcome = "created" if result.created else "already configured"
    print(f"Owner workspace {outcome}: {result.workspace.name}")


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
            if operation == "create-owner":
                create_owner(session, runtime)
            elif operation == "create":
                display_name = input("Display name: ").strip()
                create_account(
                    session,
                    display_name=display_name,
                    email=entered_email(),
                    password=confirmed_password(),
                    verified_at=datetime.now(UTC),
                )
            else:
                account = require_account(session, entered_email())
                if operation == "reset-password":
                    reset_account_password(session, account, confirmed_password())
                elif operation == "disable":
                    set_account_state(session, account, DISABLED)
                elif operation == "enable":
                    set_account_state(session, account, ACTIVE)
                else:
                    raise ValueError(f"Unsupported operation: {operation}")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Leave Planner email accounts")
    parser.add_argument(
        "operation",
        choices=("create-owner", "create", "reset-password", "disable", "enable"),
    )
    arguments = parser.parse_args()
    try:
        run(arguments.operation)
    except ValueError as error:
        parser.error(str(error))
    print(f"Account operation completed: {arguments.operation}")


if __name__ == "__main__":
    main()
