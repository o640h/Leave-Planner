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
    database pg_dump -U postgres --role=leave_planner_backup -d leave_planner \
        --format=custom --no-acl > "$partial_archive"
    database pg_restore --list < "$partial_archive" > /dev/null
    restore_archive=$partial_archive
else
    archive="$backup_dir/$(basename -- "$target")"
    [ -f "$archive.sha256" ] || fail 'Missing checksum sidecar.'
    (cd -- "$backup_dir" && sha256sum -c "$(basename -- "$archive").sha256")
    restore_archive=$archive
fi
# Cleanup owns only a successfully created, generated database, never an existing target.
candidate="leave_planner_restore_$(date -u +%Y%m%d%H%M%S)_$$"
database createdb -U postgres --template=template0 --owner=leave_planner_restore "$candidate"
restore_db=$candidate
database pg_restore -U postgres --role=leave_planner_restore --no-owner --no-acl \
    --dbname="$restore_db" --single-transaction < "$restore_archive"
partial_report="$archive.verify.partial"
database psql -X -U postgres -d "$restore_db" -v ON_ERROR_STOP=1 > "$partial_report" <<'SQL'
SET ROLE leave_planner_restore;
SELECT version_num AS schema_revision FROM alembic_version;
DO $$
BEGIN
    IF to_regclass('public.users') IS NULL
       OR to_regclass('public.user_sessions') IS NULL
       OR to_regclass('public.account_action_tokens') IS NULL
       OR to_regclass('public.workspace_memberships') IS NULL THEN
        RAISE EXCEPTION 'Identity or workspace access tables are missing from the restore';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname IN ('workspaces', 'workspace_memberships', 'consultants')
          AND relnamespace = 'public'::regnamespace
          AND NOT relrowsecurity
    ) THEN
        RAISE EXCEPTION 'Workspace row-level security was not restored';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM (VALUES
            ('workspaces', 'workspaces_select'),
            ('workspaces', 'workspaces_write'),
            ('workspace_memberships', 'workspace_memberships_select'),
            ('workspace_memberships', 'workspace_memberships_write'),
            ('consultants', 'consultants_workspace')
        ) AS required_policy(table_name, policy_name)
        WHERE NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = required_policy.table_name
              AND policyname = required_policy.policy_name
        )
    ) THEN
        RAISE EXCEPTION 'Workspace isolation policies were not restored';
    END IF;
END $$;
SELECT 'users' AS protected_table, count(*) AS restored_rows FROM users
UNION ALL SELECT 'user_sessions', count(*) FROM user_sessions
UNION ALL SELECT 'account_action_tokens', count(*) FROM account_action_tokens
UNION ALL SELECT 'workspace_memberships', count(*) FROM workspace_memberships;
SELECT format('SELECT %L AS table_name, count(*) AS restored_rows FROM %I.%I;',
              tablename, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
\gexec
SQL
database dropdb -U postgres "$restore_db"
restore_db=
if [ "$action" = backup ]; then
    mv -- "$partial_archive" "$archive"
    partial_archive=
    (cd -- "$backup_dir" && sha256sum "$(basename -- "$archive")" > "$(basename -- "$archive").sha256")
fi
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
