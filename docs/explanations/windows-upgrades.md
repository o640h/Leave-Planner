# Windows upgrades

Leave Planner upgrades in place. The operator should close the application and run the newer
`Leave-Planner-Setup-<version>.exe`; they should not uninstall the previous version first.

The installer keeps one permanent Inno Setup `AppId` and enables `UsePreviousAppDir`, so a newer
installer finds the existing installation directory and replaces the packaged application files.
The release version is supplied to the installer build:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build-installer.ps1 -Version 0.2.0
```

Application data is not stored in the installation directory. Every packaged version resolves the
same user-scoped paths:

- database: `%LOCALAPPDATA%\LeavePlanner\leave-planner.sqlite3`;
- backups: `%LOCALAPPDATA%\LeavePlanner\backups`;
- preferences: `%LOCALAPPDATA%\LeavePlanner`.

On its first start after an upgrade, the new application checks whether the existing database needs
a schema migration. It creates and verifies a pre-migration backup when required, upgrades the same
database in place, and then opens it normally. An installer upgrade must never copy, rename, delete,
or replace the `%LOCALAPPDATA%\LeavePlanner` directory.

## Release verification

For every installer release:

1. Install the previous released version and create representative consultants, preferences, leave
   years, job plans, entitlement, bookings, and backups.
2. Close Leave Planner and record the installed version, installation directory, and hashes of all
   files under `%LOCALAPPDATA%\LeavePlanner`.
3. Run the newer installer normally without uninstalling the previous version.
4. Confirm Windows reports the new version under the same installer identity and installation
   directory, while the local-data hashes remain unchanged before the new application is launched.
5. Launch the upgraded application. Confirm its health, consultant directory, configured leave
   year, calculations, bookings, preferences, and Data & Recovery entries load from the retained
   local-data directory.
6. When a schema migration is included, confirm that a verified pre-migration backup exists and the
   migrated database passes SQLite integrity and current-schema checks.
7. Confirm a subsequent backup and restore still reproduce the upgraded data.

The `0.1.0` to `0.2.0` verification used the installed release in its existing Program Files
directory. All 30 existing local-data files were byte-for-byte unchanged by the installer. The
upgraded packaged application then started successfully, reported a healthy local API, and loaded
the existing consultant and backup records from `%LOCALAPPDATA%\LeavePlanner`.
