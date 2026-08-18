"""Coordinate the local server and native Windows application window."""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import tempfile
from ctypes import WinDLL
from pathlib import Path
from time import monotonic, sleep
from typing import Literal, cast

import webview

from settings import Settings

from .instance import AlreadyRunningError, SingleInstance
from .server import start_server, wait_until_ready
from .splash import splash_html
from .windows import (
    apply_window_identity,
    apply_window_theme,
    configure_process_identity,
    configure_splash_window,
    resolve_window_theme,
)

DEVELOPMENT_FRONTEND = "http://127.0.0.1:5173"
ICON_PATH = Path(__file__).resolve().parent / "assets" / "leave-planner.ico"
CAPTION_ICON_PATH = Path(__file__).resolve().parent / "assets" / "transparent.ico"
ThemePreference = Literal["dark", "light", "system"]
ResolvedTheme = Literal["dark", "light"]
VALID_THEME_PREFERENCES = {"dark", "light", "system"}
VALID_RESOLVED_THEMES = {"dark", "light"}
SPLASH_MINIMUM_SECONDS = 3.8


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


def _configure_splash_identity(window: webview.Window, theme: ResolvedTheme) -> None:
    """Give the master splash native corners and the application taskbar identity."""

    configure_splash_window(window)
    apply_window_identity(window, ICON_PATH, CAPTION_ICON_PATH, theme)


def _reveal_application_window(
    application_window: webview.Window,
    splash_window: webview.Window,
    startup_theme: ResolvedTheme,
    startup_errors: list[Exception],
) -> None:
    """Reveal the loaded master window after the temporary splash."""

    try:
        if not application_window.events.shown.wait(10):
            raise RuntimeError("The application window could not be created.")
        apply_window_identity(
            application_window,
            ICON_PATH,
            CAPTION_ICON_PATH,
            startup_theme,
        )

        if not splash_window.events.shown.wait(10):
            raise RuntimeError("The startup window could not be displayed.")
        _configure_splash_identity(splash_window, startup_theme)
        splash_shown_at = monotonic()

        if not application_window.events.loaded.wait(10):
            raise RuntimeError("The application window did not finish loading.")

        remaining = SPLASH_MINIMUM_SECONDS - (monotonic() - splash_shown_at)
        if remaining > 0:
            sleep(remaining)

        apply_window_identity(
            application_window,
            ICON_PATH,
            CAPTION_ICON_PATH,
            startup_theme,
        )
        application_window.show()
        apply_window_identity(
            application_window,
            ICON_PATH,
            CAPTION_ICON_PATH,
            startup_theme,
        )
        sleep(0.12)
        splash_window.destroy()
    except Exception as error:
        startup_errors.append(error)
        splash_window.destroy()
        application_window.destroy()


def run_desktop(*, development: bool, devtools: bool = False) -> None:
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
        startup_errors: list[Exception] = []

        try:
            base_url = DEVELOPMENT_FRONTEND if development else server.url
            if development:
                wait_until_ready(DEVELOPMENT_FRONTEND)

            configure_process_identity()
            desktop_api = DesktopApi(settings.app_name, data_dir / "theme-preference")
            startup_screen = webview.screens[0]
            startup_theme = resolve_window_theme(desktop_api.get_theme_preference())
            splash_is_light = startup_theme == "light"
            window = webview.create_window(
                settings.app_name,
                f"{base_url}?desktop=1",
                js_api=desktop_api,
                width=1440,
                height=900,
                min_size=(900, 650),
                screen=startup_screen,
                hidden=True,
                resizable=True,
                frameless=False,
                shadow=True,
                background_color="#fbfcfc" if splash_is_light else "#101010",
            )
            if window is None:
                raise RuntimeError("The desktop window could not be created.")
            desktop_api._attach_window(window)

            splash = webview.create_window(
                f"{settings.app_name} Startup",
                html=splash_html(light=splash_is_light, icon_path=ICON_PATH),
                width=400,
                height=280,
                screen=startup_screen,
                resizable=False,
                frameless=True,
                easy_drag=True,
                shadow=True,
                on_top=True,
                transparent=False,
                background_color="#fbfcfc" if splash_is_light else "#181818",
            )
            if splash is None:
                raise RuntimeError("The startup window could not be created.")
            splash.events.before_show += lambda: _configure_splash_identity(
                splash,
                startup_theme,
            )

            webview.start(
                func=_reveal_application_window,
                args=(
                    window,
                    splash,
                    startup_theme,
                    startup_errors,
                ),
                gui="edgechromium",
                debug=devtools,
            )
        finally:
            server.stop()

        if startup_errors:
            raise startup_errors[0]


def main() -> int:
    """Run the desktop application the command line."""

    parser = argparse.ArgumentParser(description="Run Leave Planner as a desktop application.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use the Vite development frontend with hot reload.",
    )
    parser.add_argument(
        "--devtools",
        action="store_true",
        help="Open WebView2 developer tools alongside the development frontend.",
    )
    arguments = parser.parse_args()
    development = bool(arguments.dev)
    devtools = bool(arguments.devtools and development)

    try:
        run_desktop(development=development, devtools=devtools)
    except AlreadyRunningError as error:
        show_error(str(error))
        return 1
    except Exception as error:
        show_error(f"Leave Planner could not start.\n\n{error}")
        return 1

    return 0
