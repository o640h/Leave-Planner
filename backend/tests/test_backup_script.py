"""Exercise backup orchestration failures without connecting to any real database."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "PostgresBackup.sh"


def shell_path(path: Path) -> str:
    value = path.as_posix()
    return f"/{value[0].lower()}{value[2:]}" if path.drive else value


@pytest.mark.parametrize("failure", ["", "pg_dump", "createdb", "restore", "psql"])
def test_backup_publishes_only_after_restore_and_cleans_only_owned_database(
    tmp_path: Path,
    failure: str,
) -> None:
    bash = (
        shutil.which("bash")
        if os.name != "nt"
        else str(Path(os.environ["LOCALAPPDATA"]) / "Programs/Git/bin/bash.exe")
    )
    if not bash or not Path(bash).is_file():
        pytest.skip("Requires bash (Git for Windows or native Linux)")
    mock_dir = tmp_path / "commands"
    mock_dir.mkdir()
    backups = tmp_path / "backups"
    backups.mkdir()
    log = tmp_path / "calls.txt"
    docker = mock_dir / "docker"
    docker.write_text(
        """#!/bin/sh
while [ "$1" != database ]; do shift; done
shift
printf '%s\\n' "$*" >> "$TEST_LOG"
command=$1
if [ "$command" = "$FAIL_COMMAND" ]; then exit 1; fi
case "$command" in
 pg_dump) printf 'test archive' ;;
 pg_restore)
   cat > /dev/null
   if [ "$2" != --list ] && [ "$FAIL_COMMAND" = restore ]; then exit 1; fi ;;
 psql) cat > /dev/null; printf 'restored table counts' ;;
esac
""",
        encoding="utf-8",
        newline="\n",
    )
    docker.chmod(0o700)
    result = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-c",
            'export PATH="$1:/usr/bin:/bin"; sh "$2" backup "$3"',
            "backup-test",
            shell_path(mock_dir),
            shell_path(SCRIPT),
            shell_path(backups),
        ],
        env={**os.environ, "FAIL_COMMAND": failure, "TEST_LOG": shell_path(log)},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == (1 if failure else 0), result.stderr
    assert bool(list(backups.glob("*.verified.txt"))) is (not failure)
    assert not (backups / ".leave-planner-backup-lock").exists()
    calls = log.read_text(encoding="utf-8")
    assert "pg_dump -U postgres --role=leave_planner_backup" in calls
    assert "--format=custom --no-acl" in calls
    if failure not in {"pg_dump", "createdb"}:
        assert "pg_restore -U postgres --role=leave_planner_restore --no-owner" in calls
        assert "--no-acl" in calls
    drops = [line for line in calls.splitlines() if line.startswith("dropdb")]
    assert bool(drops) is (failure not in {"pg_dump", "createdb"})
    assert all("leave_planner_restore_" in line for line in drops)
    if failure:
        assert not list(backups.glob("*.dump"))
        assert not list(backups.glob("*.sha256"))
