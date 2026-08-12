"""Small Windows integrations that pywebview does not provide during development."""

from __future__ import annotations

from ctypes import WinDLL, byref, c_int, c_void_p, sizeof
from ctypes.wintypes import HWND, LPARAM, LPCWSTR, UINT, WPARAM
from pathlib import Path
from typing import Any

APPLICATION_ID = "LeavePlanner.Desktop"
IMAGE_ICON = 1
ICON_SMALL = 0
ICON_BIG = 1
LR_LOADFROMFILE = 0x0010
WM_SETICON = 0x0080
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def _colour_ref(red: int, green: int, blue: int) -> int:
    return red | (green << 8) | (blue << 16)


def configure_process_identity() -> None:
    """Separate Leave Planner from the Python host in the Windows taskbar."""

    shell32 = WinDLL("shell32", use_last_error=True)
    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [LPCWSTR]
    shell32.SetCurrentProcessExplicitAppUserModelID.restype = c_int
    shell32.SetCurrentProcessExplicitAppUserModelID(APPLICATION_ID)


def _window_handle(window_title: str) -> tuple[Any, HWND]:
    user32 = WinDLL("user32", use_last_error=True)
    user32.FindWindowW.argtypes = [LPCWSTR, LPCWSTR]
    user32.FindWindowW.restype = HWND
    return user32, user32.FindWindowW(None, window_title)


def apply_window_theme(window_title: str, theme: str) -> None:
    """Match the native caption to the resolved application theme."""

    _, window_handle = _window_handle(window_title)
    if not window_handle:
        return

    dark = theme != "light"
    caption = (13, 13, 13) if dark else (233, 237, 240)
    border = (37, 37, 37) if dark else (205, 212, 217)
    dwmapi = WinDLL("dwmapi", use_last_error=True)
    dwmapi.DwmSetWindowAttribute.argtypes = [HWND, UINT, c_void_p, UINT]
    dwmapi.DwmSetWindowAttribute.restype = c_int
    for attribute, raw_value in (
        (DWMWA_USE_IMMERSIVE_DARK_MODE, int(dark)),
        (DWMWA_BORDER_COLOR, _colour_ref(*border)),
        (DWMWA_CAPTION_COLOR, _colour_ref(*caption)),
        (DWMWA_TEXT_COLOR, _colour_ref(*caption)),
    ):
        value = c_int(raw_value)
        dwmapi.DwmSetWindowAttribute(window_handle, attribute, byref(value), sizeof(value))


def apply_window_identity(
    window_title: str, icon_path: Path, caption_icon_path: Path
) -> None:
    """Apply taskbar identity while leaving the native caption visually quiet."""

    user32, window_handle = _window_handle(window_title)
    user32.LoadImageW.argtypes = [c_void_p, LPCWSTR, UINT, c_int, c_int, UINT]
    user32.LoadImageW.restype = c_void_p
    user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    user32.SendMessageW.restype = LPARAM

    if not window_handle:
        return

    apply_window_theme(window_title, "dark")

    for icon_kind, size, source in (
        (ICON_SMALL, 16, caption_icon_path),
        (ICON_BIG, 32, icon_path),
    ):
        icon = user32.LoadImageW(
            None,
            str(source),
            IMAGE_ICON,
            size,
            size,
            LR_LOADFROMFILE,
        )
        if icon:
            user32.SendMessageW(window_handle, WM_SETICON, icon_kind, icon)
