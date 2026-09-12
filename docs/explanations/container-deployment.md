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
  the internal database network and a separate edge network. The NAS publishes port `8080` on its
  loopback interface only, so the selected host-level HTTPS tunnel or proxy can reach it but LAN and
  internet clients cannot bypass HTTPS.

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

Copy `deploy/.env.example` to `deploy/.env` on the deployment host. Its values bind port `8080`
to `127.0.0.1` and configure the exact public origin. Compose and production startup both refuse
to run without that HTTPS origin. Change it when the public hostname changes; do not add aliases
casually because the same value anchors host validation and CSRF origin checks.

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

During initial LAN-only acceptance, health was checked directly from a LAN computer. After the
hosted boundary is deployed, use the HTTPS hostname instead:

```powershell
Invoke-RestMethod "https://app.merydio.co.uk/api/health"
```

The expected result is `status: ok` and `environment: production`. Direct
`http://192.168.1.253:8080` access is intentionally unavailable.

## Public HTTPS edge

The production edge is Cloudflare Tunnel at `https://app.merydio.co.uk`. Cloudflare terminates
trusted public TLS and carries requests over an outbound connector to `http://application:8000` on
the private edge network. The application accepts that exact public host, limits requests to 1 MiB,
applies per-client and stricter login throttles, and emits the browser security headers. Manage the
connector with both Compose files and follow `custom-domain.md` for token handling and recovery.

Do not create a Leave Planner router forwarding rule or enable DMZ. Do not expose DSM administration,
port `8080`, PostgreSQL, Container Manager, or SSH. During acceptance the EE Hub's custom port
forwarding proved nonfunctional even though an existing Plex UPnP mapping worked, so all temporary
Leave Planner mappings were removed. Synology DDNS, its certificate, and the DSM reverse proxy were
validated locally but are not part of the selected public route.

The earlier Tailscale Funnel was a proof of concept and is no longer the production route. Disable
its DSM update task and uninstall the package after confirming it is not used for private NAS
administration.

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

The normal NAS release is initiated from the repository root in the VS Code PowerShell terminal:

```powershell
.\scripts\DeployToNas.ps1 -Version 0.2.2
```

Use a new semantic version for every attempt; deployed release directories and image tags are
immutable. The script runs the complete local backend and frontend checks, creates a source archive
that excludes local environments and secrets, uploads it with Synology-compatible legacy SCP, and
invokes the NAS-side release helper. SSH and sudo can request the operator password.
The PowerShell script runs `DeployRelease.sh` automatically; do not invoke the NAS helper separately.

On the NAS, the helper extracts to `releases/VERSION`, links only the persistent deployment `.env`
and secret directory, creates and restores a pre-release database dump, builds
`leave-planner:VERSION`, runs migrations, switches the application, confirms container health, and
updates the `current` source link. PostgreSQL and the Cloudflare connector are not recreated. The
previous image is retained and no image or volume prune is performed. After the first scripted
release, use `/volume1/docker/leave-planner/current/deploy` for source-relative manual diagnostics.

`-SkipChecks` exists for a repeat invocation only when the identical source has already passed the
checks; ordinary releases must not use it. Optional connection parameters are available through
`Get-Help .\scripts\DeployToNas.ps1 -Detailed` or the script parameter list.

For diagnosis or a deliberately manual reviewed release, the underlying sequence remains:

```powershell
docker compose --file deploy/compose.yml --file deploy/compose.cloudflare.yml build --pull application
docker compose --file deploy/compose.yml --file deploy/compose.cloudflare.yml run --rm migrate
docker compose --file deploy/compose.yml --file deploy/compose.cloudflare.yml up --detach --no-deps application
docker compose --file deploy/compose.yml --file deploy/compose.cloudflare.yml ps --all
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
