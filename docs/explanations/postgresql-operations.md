# PostgreSQL Operations

## Where the database lives

The named volume `leave-planner_postgres_data` holds PostgreSQL's directory of files, not a
single SQLite file. Its container mount is `/var/lib/postgresql/data`. Find its NAS location:

```sh
sudo docker volume inspect leave-planner_postgres_data --format '{{.Mountpoint}}'
```

Rebuilding the app preserves this volume. Do not rename the Compose project, prune volumes,
use `docker compose down --volumes`, or select a Container Manager option that deletes volumes.
Do not copy the running data directory as a backup.

## Agreed backup boundary

The operator chose **NAS-only storage**, superseding the earlier off-device-copy requirement.
Dumps protect against accidental changes and failed releases, but cannot recover from loss,
theft, compromise or failure of the whole NAS. Spare capacity and RAID do not remove that risk.
Revisit this accepted limitation before storing irreplaceable live records.

## Operator setup

1. Create a DSM shared folder `leave-planner-backups` on Volume 1, separate from the source
   deployment folder. Restrict access to administrators. Enable shared-folder encryption if
   available and retain its recovery key securely, never in Git.
2. Upload `scripts/PostgresBackup.sh` to the project's `scripts` directory with LF line endings.
3. In **NAS SSH**, run:

```sh
sudo sh /volume1/docker/leave-planner/scripts/PostgresBackup.sh backup /volume1/leave-planner-backups
```

Each backup uses the existing PostgreSQL container's tools. It creates a custom-format dump and
checksum, restores the complete archive transactionally into a newly generated temporary database,
reads every table, then removes that temporary database. Only then is a `.verified.txt` report
published. It never restores over `leave_planner`. This checks database restoration, not browser
behaviour. Only restore trusted archives: a PostgreSQL archive contains executable SQL.

4. Create a DSM Task Scheduler **User-defined script**, user **root**, daily at **02:00**:

```sh
PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin
export PATH
sh /volume1/docker/leave-planner/scripts/PostgresBackup.sh backup /volume1/leave-planner-backups
```

Enable and test failure notifications. Keep task output private: database-tool errors may contain
SQL. The recovery-point target is 24 hours **provided daily jobs succeed**. Verified archive sets
older than 30 days are pruned only after a new successful restore. Partial files remain for
investigation. After an interrupted job, check no backup is running before removing a stale
`.leave-planner-backup-lock` directory. Do not remove the backup folder itself.

## Restore acceptance and recovery

Recheck a specific archive using its exact filename:

```sh
sudo sh /volume1/docker/leave-planner/scripts/PostgresBackup.sh verify /volume1/leave-planner-backups/EXACT-ARCHIVE.dump
```

Before accepting live recovery, also restore to a separate unpublished recovery deployment using
the same PostgreSQL major version, role names and application image. Compare accounts/workspace
isolation, consultants/years, entitlement and booking totals, audit history and a PDF export against
pre-backup examples. Test sign-in locally. Never connect this recovery deployment to the public
tunnel. Record restore duration; the initial recovery-time target is two hours, not a measured
guarantee. This application-level acceptance is still an operator checkpoint.

Actual production replacement requires an administrator maintenance window: stop writes, preserve
the current database and latest dump, restore into a new volume/deployment, verify, then switch the
private route. Do not improvise an in-place overwrite. Dumps exclude role passwords, `.env`, tunnel
tokens and images. Keep a restricted NAS copy of configuration/secrets and the previous app image.
Reinitialisation must recreate the existing role names through `deploy/postgres/init-database.sh`.

## Safe release

Use `scripts/DeployToNas.ps1 -Version VERSION` from the local repository. It stages source in a
versioned NAS directory without overwriting `.env`, `secrets`, or backups, records the current image,
creates and restore-verifies a pre-release dump, and builds a distinct version tag before migration.
The previous image is retained rather than overwritten.

```sh
export LEAVE_PLANNER_VERSION=0.2.2
sudo docker compose -f compose.yml -f compose.cloudflare.yml build --pull application
sudo docker compose stop application
sudo docker compose -f compose.yml -f compose.cloudflare.yml run --rm migrate
# Continue only if migration succeeds:
sudo docker compose -f compose.yml -f compose.cloudflare.yml up -d --no-deps application
sudo docker compose -f compose.yml -f compose.cloudflare.yml ps
sudo docker compose -f compose.yml -f compose.cloudflare.yml logs --tail=100 application
```

On migration failure, preserve output privately and do not launch the new app. Restart an old image
only if compatible with the resulting schema; otherwise use the pre-release recovery deployment.
PostgreSQL major upgrades require a separate dump/restore plan, not just an image-tag change.

## Ownership and monitoring

The operator owns weekly checks of backup success, latest archive age, restore duration, container
health/restarts, and DSM Storage Manager alerts. Configure and test DSM capacity and health
notifications; start with a warning at 20% free capacity. Review app, PostgreSQL, cloudflared and
tunnel versions monthly and act promptly on relevant security advisories. Keep log rotation enabled.
Never log request bodies/passwords/tokens or share unredacted production logs.

Live logs: `sudo docker compose logs --follow --tail=100 application`. Ctrl+C stops viewing, not
the service. Health checks alone do not restart unhealthy containers; investigate explicitly.
No NAS reboot is required.

Reference: [PostgreSQL restore options](https://www.postgresql.org/docs/17/app-pgrestore.html).
