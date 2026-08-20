# Reproducible Container Deployment

## Runtime boundary

The production image builds the React application with the locked npm dependency tree, installs only
the backend runtime dependency group, and serves the compiled assets from FastAPI. The final image
contains no Node runtime, frontend source, backend tests, desktop shell, pywebview, PyInstaller, or
development dependency group. It runs as the unprivileged numeric identity `10001:10001` with a
read-only root filesystem.

The Compose project has three services:

- `database` is pinned to PostgreSQL 17.10. Its port is not published, its data is held in the named
  `postgres_data` volume, and only the internal database network can reach it.
- `migrate` is a one-shot release service. It uses the schema-owner credential, runs Alembic, verifies
  the resulting revision, and must finish successfully before the application may start.
- `application` uses a separate runtime credential with data access but no schema ownership. It joins
  the internal database network and a separate edge network, and publishes port `8080` for LAN-only
  Task 8 acceptance.

Normal development remains unchanged: Vite runs on `localhost:5173`, FastAPI runs on
`127.0.0.1:8000`, and the development server upgrades its isolated SQLite schema automatically.
Production never upgrades implicitly. It exits with a clear error if the migration service was not
run successfully.

## Secret files

Generate the five deployment secret files once from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\NewDeploymentSecrets.ps1"
```

The files are written under `deploy/secrets` without printing their contents. They are excluded from
Git and the Docker build context. Transfer that directory to the NAS separately and do not paste its
contents into source files, screenshots, logs, chat, or commits.

Never run the generator with `-Force` after PostgreSQL has initialized its persistent volume. Merely
changing these files does not rotate database-role passwords; it instead makes the application unable
to connect. Credential rotation belongs in the separately controlled operations work.

## Configuration validation

Docker Compose can validate the complete merged configuration without starting a container:

```powershell
docker compose --file deploy/compose.yml config --quiet
```

The optional values in `deploy/.env.example` default to LAN port `8080` on all NAS interfaces. No
router forwarding is configured, so this is reachable only from the current private network during
Task 8. Task 9 will replace direct LAN access with the Synology HTTPS reverse proxy.

## Initial release commands

From a terminal in the repository root on a Docker host:

```powershell
docker compose --file deploy/compose.yml build --pull
docker compose --file deploy/compose.yml up --detach --wait
docker compose --file deploy/compose.yml ps --all
docker compose --file deploy/compose.yml logs migrate
```

The first command builds the exact same application image for `migrate` and `application`. On first
startup PostgreSQL creates separate migrator and application roles from the mounted secrets. The
migration container then upgrades the empty database and exits successfully; only then does the
application start.

Check health from a LAN computer:

```powershell
Invoke-RestMethod "http://192.168.1.253:8080/api/health"
```

The expected result is `status: ok` and `environment: production`. The frontend is also served at
`http://192.168.1.253:8080`, but production cookies deliberately require HTTPS. Full Admin sign-in is
therefore accepted through the HTTPS address established in Task 9, rather than weakening cookie
security for this temporary HTTP check.

Create the fixed account once after migration:

```powershell
docker compose --file deploy/compose.yml exec application python -m authentication.admin create
```

This is an interactive server-owner command and does not accept the password as a command-line
argument. In Synology Container Manager, the equivalent is opening the application container's
terminal and running `python -m authentication.admin create`.

## Persistence and restart acceptance

These commands exercise increasingly broad restart behavior while preserving PostgreSQL data:

```powershell
docker compose --file deploy/compose.yml restart application
docker compose --file deploy/compose.yml up --detach --force-recreate --no-deps application
docker compose --file deploy/compose.yml down
docker compose --file deploy/compose.yml up --detach --wait
```

After each operation, check `ps --all`, the application/database health, and the presence of the Admin
account. A DSM reboot then proves that the `unless-stopped` database and application services return
without rerunning a hidden migration. The completed migration container is intentionally not a
long-running service. If an established NAS uptime must not be interrupted during development,
record the reboot check as deferred and perform it during the hosted acceptance gate's planned
maintenance window; never report an unperformed reboot as verified.

`docker compose down` preserves the named volume. Never add `--volumes` or run `docker volume rm`
against this project: those operations delete the database. Task 10 will add verified dumps and a
restore drill before real consultant data is hosted.

## Application upgrade

For a reviewed release whose image version and migration set have been updated:

```powershell
docker compose --file deploy/compose.yml build --pull application
docker compose --file deploy/compose.yml run --rm migrate
docker compose --file deploy/compose.yml up --detach --no-deps application
docker compose --file deploy/compose.yml ps --all
```

If migration fails, keep the existing application release stopped or unchanged and inspect
`docker compose --file deploy/compose.yml logs migrate`. Do not bypass the migration failure by
starting a newer application against the older schema.

## Resource envelope

The application is limited to 512 MB RAM. PostgreSQL is limited to 1.5 GB RAM with a 128 MB
shared-memory allocation. The DS225+ kernel rejects Docker's CFS-based `NanoCPUs` limit and does not
mount the cgroup support required for Docker PID limits, so this deployment does not set misleading
CPU or process quotas. This leaves most of the NAS's 6 GB RAM available to DSM and other services,
while CPU and process use must be observed through Container Manager statistics during acceptance.
Sustained pressure or restarts are reasons to stop and adjust before external access.
