"""Server-owner command for importing an existing SQLite database."""

import argparse
from pathlib import Path

from settings import Settings

from .service import import_sqlite_database


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a verified Leave Planner SQLite database into PostgreSQL"
    )
    parser.add_argument("--source", type=Path, required=True, help="Existing SQLite database path")
    parser.add_argument(
        "--backup-directory",
        type=Path,
        help="Directory for the verified pre-import SQLite backup",
    )
    arguments = parser.parse_args()

    settings = Settings()
    report = import_sqlite_database(
        arguments.source,
        settings.resolved_database_url,
        backup_directory=arguments.backup_directory,
    )
    outcome = "already completed" if report.already_completed else "completed"
    print(f"SQLite import {outcome}.")
    print(f"Verified backup: {report.backup_path}")
    print(f"Source SHA-256: {report.source_sha256}")
    print(f"Consultant years reconciled: {report.consultant_years}")
    for table_name, count in sorted(report.table_counts.items()):
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
