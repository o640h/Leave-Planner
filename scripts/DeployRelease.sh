#!/bin/sh
# Internal NAS-side release helper. Invoke through DeployToNas.ps1, not directly.
set -eu
umask 077

# Synology's sudo shell uses a restricted PATH that can omit Container Manager's CLI links.
PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/packages/ContainerManager/target/usr/bin:${PATH:-}"
export PATH

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

[ "$#" -eq 4 ] || fail 'Expected VERSION ARCHIVE REMOTE_ROOT BACKUP_DIRECTORY.'
command -v docker >/dev/null 2>&1 || fail 'Docker was not found in the Synology Container Manager paths.'
docker compose version >/dev/null 2>&1 || fail 'The Docker Compose plugin is unavailable.'
version=$1
archive=$2
root_dir=$3
backup_dir=$4

case "$version" in
    ''|*[!0-9A-Za-z.-]*|.*|*..*) fail 'Invalid release version.' ;;
esac
case "$root_dir" in
    /volume[0-9]/*) ;;
    *) fail 'The release root must be a specific directory beneath /volumeN.' ;;
esac
case "$backup_dir" in
    /volume[0-9]/*) ;;
    *) fail 'The backup directory must be a specific directory beneath /volumeN.' ;;
esac

[ -f "$archive" ] || fail 'The uploaded release archive is missing.'
[ -f "$root_dir/deploy/.env" ] || fail 'The persistent deployment .env file is missing.'
[ -d "$root_dir/deploy/secrets" ] || fail 'The persistent deployment secrets directory is missing.'
[ -s "$root_dir/deploy/secrets/resend_api_key.txt" ] || fail 'The Resend API key secret is missing or empty.'
[ -d "$backup_dir" ] || fail 'The restricted NAS backup directory is missing.'

releases_dir="$root_dir/releases"
release_dir="$releases_dir/$version"
[ ! -e "$release_dir" ] || fail 'This immutable release version already exists on the NAS.'

completed=false
cleanup() {
    result=$?
    trap - EXIT
    rm -f -- "$archive" "$0"
    if [ "$completed" != true ] && [ -d "$release_dir" ]; then
        rm -rf -- "$release_dir"
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

mkdir -p -- "$releases_dir"
mkdir -- "$release_dir"
tar -xzf "$archive" -C "$release_dir"

[ -f "$release_dir/deploy/compose.yml" ] || fail 'The release does not contain deploy/compose.yml.'
[ -f "$release_dir/deploy/compose.cloudflare.yml" ] || fail 'The Cloudflare Compose overlay is missing.'
[ -f "$release_dir/scripts/PostgresBackup.sh" ] || fail 'The backup helper is missing.'
[ -f "$release_dir/scripts/ConfigureDatabaseRoles.sh" ] || fail 'The database-role helper is missing.'

ln -s "$root_dir/deploy/.env" "$release_dir/deploy/.env"
ln -s "$root_dir/deploy/secrets" "$release_dir/deploy/secrets"

deploy_dir="$release_dir/deploy"
compose() {
    docker compose --project-directory "$deploy_dir" \
        -f "$deploy_dir/compose.yml" \
        -f "$deploy_dir/compose.cloudflare.yml" "$@"
}

export LEAVE_PLANNER_VERSION="$version"
previous_image=$(docker inspect leave-planner-application-1 --format '{{.Config.Image}}' 2>/dev/null || true)
previous_image_id=$(docker inspect leave-planner-application-1 --format '{{.Image}}' 2>/dev/null || true)

printf 'Creating and verifying the pre-release database backup...\n'
sh "$release_dir/scripts/ConfigureDatabaseRoles.sh"
sh "$release_dir/scripts/PostgresBackup.sh" backup "$backup_dir"

printf 'Building application image leave-planner:%s...\n' "$version"
compose build --pull application

printf 'Running database migrations...\n'
compose run --rm migrate

printf 'Switching the application without recreating PostgreSQL or the Cloudflare connector...\n'
compose up -d --no-deps application

application_id=$(compose ps -q application)
[ -n "$application_id" ] || fail 'Compose did not create the application container.'

attempt=0
while [ "$attempt" -lt 36 ]; do
    health=$(docker inspect "$application_id" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}')
    case "$health" in
        healthy) break ;;
        unhealthy|exited|dead)
            compose logs --tail=100 application >&2
            fail "The application entered state: $health"
            ;;
    esac
    attempt=$((attempt + 1))
    sleep 5
done
[ "$health" = healthy ] || fail 'The application did not become healthy within three minutes.'

env_file="$root_dir/deploy/.env"
if grep -q '^LEAVE_PLANNER_VERSION=' "$env_file"; then
    sed -i "s/^LEAVE_PLANNER_VERSION=.*/LEAVE_PLANNER_VERSION=$version/" "$env_file"
else
    printf '\nLEAVE_PLANNER_VERSION=%s\n' "$version" >> "$env_file"
fi

ln -sfn "$release_dir" "$root_dir/current"
completed=true

printf 'Release %s is healthy.\n' "$version"
if [ -n "$previous_image" ]; then
    printf 'Previous image retained for controlled rollback: %s (%s)\n' "$previous_image" "$previous_image_id"
fi
