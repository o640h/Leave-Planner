"""Coordinate the local server and native Windows application window."""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import tempfile
from ctypes import WinDLL
from pathlib import Path
from typing import Literal, cast

import webview

from settings import Settings

from .instance import AlreadyRunningError, SingleInstance
from .server import start_server, wait_until_ready
from .windows import apply_window_identity, apply_window_theme, configure_process_identity

DEVELOPMENT_FRONTEND = "http://127.0.0.1:5173"
ICON_PATH = Path(__file__).resolve().parent / "assets" / "leave-planner.ico"
CAPTION_ICON_PATH = Path(__file__).resolve().parent / "assets" / "transparent.ico"
ThemePreference = Literal["dark", "light", "system"]
ResolvedTheme = Literal["dark", "light"]
VALID_THEME_PREFERENCES = {"dark", "light", "system"}
VALID_RESOLVED_THEMES = {"dark", "light"}


class DesktopApi:
    """Expose the small native operations controlled by the React shell."""

    def __init__(self, window_title: str, preference_path: Path) -> None:
        self.window_title = window_title
        self.preference_path = preference_path
        self._window: webview.Window | None = None

    def _attach_window(self, window: webview.Window) -> None:
        self._window = window

    def get_theme_preference(self) -> ThemePreference | None:
        try:
            saved = self.preference_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return cast(ThemePreference, saved) if saved in VALID_THEME_PREFERENCES else None

    def set_theme(self, preference: str, resolved_theme: str) -> None:
        if preference not in VALID_THEME_PREFERENCES or resolved_theme not in VALID_RESOLVED_THEMES:
            return
        self.preference_path.write_text(preference, encoding="utf-8")
        apply_window_theme(self.window_title, resolved_theme)

    def save_pdf(self, default_filename: str, encoded_pdf: str) -> str:
        """Open a native Save As dialog and atomically write one PDF."""

        if self._window is None:
            raise RuntimeError("The desktop window is not ready")
        if Path(default_filename).name != default_filename or not default_filename.lower().endswith(
            ".pdf"
        ):
            raise ValueError("A plain PDF filename is required")
        if len(encoded_pdf) > 14_000_000:
            raise ValueError("The PDF is too large to save")
        try:
            content = base64.b64decode(encoded_pdf, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("The PDF content is invalid") from error
        if not content.startswith(b"%PDF-") or len(content) > 10_000_000:
            raise ValueError("The PDF content is invalid")

        selected = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=default_filename,
            file_types=("PDF Files (*.pdf)",),
        )
        if not selected:
            return "cancelled"

        destination = Path(selected[0]).expanduser().resolve()
        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")
        if not destination.parent.is_dir():
            raise ValueError("The selected folder is not available")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=f".{destination.stem}-",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return "saved"


def show_error(message: str) -> None:
    """Display a native Windows error dialog."""

    user32 = WinDLL("user32", use_last_error=True)
    user32.MessageBoxW(
        None,
        message,
        "Leave Planner",
        0x10,
    )


def run_desktop(*, development: bool) -> None:
    """Start FastAPI and display Leave Planner in WebView2."""

    settings = Settings(
        environment="development" if development else "production",
    )
    data_dir = settings.resolved_data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    frontend_dist = settings.resolved_frontend_dist

    if not development and not (frontend_dist / "index.html").is_file():
        raise RuntimeError(
            "The compiled frontend was not found. Run the frontend production build first."
        )

    with SingleInstance(data_dir / "instance.lock"):
        server = start_server(
            settings,
            frontend_dist,
            preferred_port=settings.port if development else None,
        )

        try:
            base_url = DEVELOPMENT_FRONTEND if development else server.url
            window_url = f"{base_url}?desktop=1"

            if development:
                wait_until_ready(DEVELOPMENT_FRONTEND)

            configure_process_identity()
            desktop_api = DesktopApi(settings.app_name, data_dir / "theme-preference")
            window = webview.create_window(
                settings.app_name,
                window_url,
                js_api=desktop_api,
                width=1440,
                height=900,
                min_size=(900, 650),
                resizable=True,
                frameless=False,
                shadow=True,
                background_color="#101010",
            )
            if window is None:
                raise RuntimeError("The desktop window could not be created.")
            desktop_api._attach_window(window)

            window.events.shown += lambda: apply_window_identity(
                settings.app_name,
                ICON_PATH,
                CAPTION_ICON_PATH,
            )
            webview.start(
                gui="edgechromium",
                debug=development,
            )
        finally:
            server.stop()


def main() -> int:
    """Run the desktop application the command line."""

    parser = argparse.ArgumentParser(description="Run Leave Planner as a desktop application.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use the Vite development frontend with hot reload.",
    )
    development = bool(parser.parse_args().dev)

    try:
        run_desktop(development=development)
    except AlreadyRunningError as error:
        show_error(str(error))
        return 1
    except Exception as error:
        show_error(f"Leave Planner could not start.\n\n{error}")
        return 1

    return 0
