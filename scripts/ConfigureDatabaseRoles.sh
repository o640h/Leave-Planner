#!/bin/sh
# Run on the NAS host before backup or migration to retain least-privilege database roles.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
deploy_dir=$(CDPATH= cd -- "$script_dir/../deploy" && pwd)
docker compose --project-directory "$deploy_dir" -f "$deploy_dir/compose.yml" \
    exec -T database psql -X -U postgres -d leave_planner -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leave_planner_backup') THEN
        CREATE ROLE leave_planner_backup NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leave_planner_restore') THEN
        CREATE ROLE leave_planner_restore NOLOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END
$$;
ALTER ROLE leave_planner_backup NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
ALTER ROLE leave_planner_restore NOLOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT CONNECT ON DATABASE leave_planner TO leave_planner_backup;
GRANT pg_read_all_data TO leave_planner_backup;
SQL
