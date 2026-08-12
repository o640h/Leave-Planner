"""Focused checks for the local desktop runtime."""

from pathlib import Path

from desktop_shell.instance import SingleInstance
from desktop_shell.launcher import CAPTION_ICON_PATH, ICON_PATH, DesktopApi
from desktop_shell.server import available_port, start_server
from settings import Settings


def test_desktop_icon_assets_are_available() -> None:
    """Both the taskbar mark and quiet caption icon must ship with the app."""

    assert ICON_PATH.is_file()
    assert CAPTION_ICON_PATH.is_file()


def test_single_instance_releases_its_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "instance.lock"

    # Reopening the same lock after the first context exits proves cleanup occurred.
    with SingleInstance(lock_path):
        assert lock_path.exists()

    with SingleInstance(lock_path):
        assert lock_path.exists()


def test_desktop_theme_preference_survives_between_api_instances(tmp_path: Path) -> None:
    preference_path = tmp_path / "theme-preference"
    first_instance = DesktopApi("Missing Test Window", preference_path)

    first_instance.set_theme("light", "light")

    assert DesktopApi("Missing Test Window", preference_path).get_theme_preference() == "light"


def test_local_server_uses_loopback_and_stops_cleanly(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path / "data")
    server = start_server(settings, tmp_path / "missing-frontend")

    try:
        assert server.url == f"http://127.0.0.1:{server.port}"
        assert server.port > 0
        assert server.thread.is_alive()
    finally:
        server.stop()

    assert not server.thread.is_alive()
    assert available_port() > 0
