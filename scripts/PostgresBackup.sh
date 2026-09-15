#!/bin/sh
# Run on the NAS host. Never restores over the live database.
set -eu
umask 077
fail() { printf '%s\n' "$*" >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
deploy_dir=$(CDPATH= cd -- "$script_dir/../deploy" && pwd)
compose() { docker compose --project-directory "$deploy_dir" -f "$deploy_dir/compose.yml" "$@"; }
database() { compose exec -T database "$@"; }
action=${1:-}
target=${2:-}
case "$action" in
    backup) [ -d "$target" ] || fail 'Create the restricted NAS backup shared folder first.'
        backup_dir=$(CDPATH= cd -- "$target" && pwd) ;;
    verify) [ -f "$target" ] || fail 'Supply an existing trusted backup archive.'
        backup_dir=$(CDPATH= cd -- "$(dirname -- "$target")" && pwd) ;;
    *) fail 'Usage: sh scripts/PostgresBackup.sh backup DIRECTORY | verify ARCHIVE' ;;
esac
lock="$backup_dir/.leave-planner-backup-lock"
mkdir "$lock" 2>/dev/null || fail 'Another backup is running, or a stale lock needs inspection.'
restore_db=
partial_archive=
partial_report=
cleanup() {
    result=$?
    trap - EXIT
    [ -z "$partial_archive" ] || rm -f -- "$partial_archive"
    [ -z "$partial_report" ] || rm -f -- "$partial_report"
    if [ -n "$restore_db" ]; then
        if ! database dropdb -U postgres --if-exists "$restore_db"; then
            printf 'Restore database cleanup failed: %s\n' "$restore_db" >&2
            result=1
        fi
    fi
    rmdir "$lock"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
stamp=$(date -u +%Y%m%dT%H%M%SZ)
if [ "$action" = backup ]; then
    archive="$backup_dir/leave-planner-$stamp-$$.dump"
    partial_archive="$archive.partial"
    database pg_dump -U postgres --role=leave_planner_backup -d leave_planner --format=custom > "$partial_archive"
    database pg_restore --list < "$partial_archive" > /dev/null
    mv -- "$partial_archive" "$archive"
    partial_archive=
    (cd -- "$backup_dir" && sha256sum "$(basename -- "$archive")" > "$(basename -- "$archive").sha256")
else
    archive="$backup_dir/$(basename -- "$target")"
    [ -f "$archive.sha256" ] || fail 'Missing checksum sidecar.'
    (cd -- "$backup_dir" && sha256sum -c "$(basename -- "$archive").sha256")
fi
# Cleanup owns only a successfully created, generated database, never an existing target.
candidate="leave_planner_restore_$(date -u +%Y%m%d%H%M%S)_$$"
database createdb -U postgres --template=template0 --owner=leave_planner_restore "$candidate"
restore_db=$candidate
database pg_restore -U postgres --role=leave_planner_restore --no-owner --dbname="$restore_db" --single-transaction < "$archive"
partial_report="$archive.verify.partial"
database psql -X -U postgres -d "$restore_db" -v ON_ERROR_STOP=1 > "$partial_report" <<'SQL'
SET ROLE leave_planner_restore;
SELECT version_num AS schema_revision FROM alembic_version;
SELECT format('SELECT %L AS table_name, count(*) AS restored_rows FROM %I.%I;',
              tablename, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
\gexec
SQL
database dropdb -U postgres "$restore_db"
restore_db=
mv -- "$partial_report" "$archive.verified.txt"
partial_report=
if [ "$action" = backup ]; then
    # Prune only our verified archive sets, after successful restoration of the new dump.
    find "$backup_dir" -maxdepth 1 -type f -name 'leave-planner-*.dump.verified.txt' -mtime +30 |
    while IFS= read -r report; do
        old_archive=${report%.verified.txt}
        rm -f -- "$old_archive" "$old_archive.sha256" "$report"
    done
fi
printf 'Verified full restore: %s\n' "$archive"
