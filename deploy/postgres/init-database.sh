#!/bin/sh
set -eu

migration_password="$(cat /run/secrets/migration_database_password)"
application_password="$(cat /run/secrets/application_database_password)"

psql --set ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set migration_password="$migration_password" \
    --set application_password="$application_password" <<'SQL'
CREATE ROLE leave_planner_migrator
    LOGIN
    PASSWORD :'migration_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT;

CREATE ROLE leave_planner_application
    LOGIN
    PASSWORD :'application_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT;

ALTER DATABASE leave_planner OWNER TO leave_planner_migrator;
GRANT CONNECT ON DATABASE leave_planner TO leave_planner_application;

GRANT USAGE ON SCHEMA public TO leave_planner_application;
ALTER DEFAULT PRIVILEGES FOR ROLE leave_planner_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO leave_planner_application;
ALTER DEFAULT PRIVILEGES FOR ROLE leave_planner_migrator IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO leave_planner_application;
SQL
