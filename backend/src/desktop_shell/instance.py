"""Prevent more than one local application instance from running."""

from __future__ import annotations

import msvcrt
from pathlib import Path
from types import TracebackType
from typing import BinaryIO


class AlreadyRunningError(RuntimeError):
    """Raised when another Leave Planner process owns the lock."""


class SingleInstance:
    """Hold a Windows file lock for the lifetime of the application."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._file: BinaryIO | None = None

    def __enter__(self) -> SingleInstance:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.lock_path.open("a+b")

        if lock_file.seek(0, 2) == 0:
            lock_file.write(b"\0")
            lock_file.flush()

        lock_file.seek(0)

        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            lock_file.close()
            raise AlreadyRunningError("Leave Planner is already running.") from error

        self._file = lock_file
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._file is None:
            return

        self._file.seek(0)
        msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        self._file.close()
        self._file = None
