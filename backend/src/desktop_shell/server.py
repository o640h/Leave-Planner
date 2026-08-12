"""Run the local FastAPI application for the desktop window."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, socket
from threading import Thread
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from main import create_app
from settings import Settings


def available_port(preferred: int | None = None) -> int:
    """Return an available loopback port."""

    with socket(AF_INET, SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", preferred or 0))
        return int(candidate.getsockname()[1])


def wait_until_ready(url: str, timeout: float = 10) -> None:
    """Wait until an HTTP endpoint responds successfully."""

    deadline = monotonic() + timeout

    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=0.25) as response:
                if response.status < 400:
                    return
        except (OSError, URLError):
            sleep(0.05)

    raise RuntimeError(f"The local application did not start within {timeout:g} seconds.")


@dataclass
class LocalServer:
    """A Uvicorn server running in a background thread."""

    server: uvicorn.Server
    thread: Thread
    port: int

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        """Request a graceful shutdown and wait briefly for completion."""

        self.server.should_exit = True
        self.thread.join(timeout=5)

        if self.thread.is_alive():
            self.server.force_exit = True
            self.thread.join(timeout=2)


def start_server(
    settings: Settings,
    frontend_dist: Path,
    *,
    preferred_port: int | None = None,
) -> LocalServer:
    """Start FastAPI and wait for its health endpoint."""

    port = available_port(preferred_port)
    app = create_app(settings=settings, frontend_dist=frontend_dist)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = Thread(
        target=server.run,
        name="leave-planner-server",
        daemon=True,
    )
    local_server = LocalServer(server=server, thread=thread, port=port)

    thread.start()

    try:
        wait_until_ready(f"{local_server.url}/api/health")
    except Exception:
        local_server.stop()
        raise

    return local_server
