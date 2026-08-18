"""Small Windows integrations that pywebview does not provide during development."""

from __future__ import annotations

from ctypes import WinDLL, byref, c_int, c_void_p, sizeof
from ctypes.wintypes import HWND, LPARAM, LPCWSTR, UINT, WPARAM
from pathlib import Path
from typing import Any, Literal
from winreg import HKEY_CURRENT_USER, OpenKey, QueryValueEx

APPLICATION_ID = "LeavePlanner.Desktop"
IMAGE_ICON = 1
ICON_SMALL = 0
ICON_BIG = 1
LR_LOADFROMFILE = 0x0010
WM_SETICON = 0x0080
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWCP_ROUND = 2
DWMWA_COLOR_NONE = 0xFFFFFFFE
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
WindowTheme = Literal["dark", "light"]


def _colour_ref(red: int, green: int, blue: int) -> int:
    return red | (green << 8) | (blue << 16)


def configure_process_identity() -> None:
    """Separate Leave Planner from the Python host in the Windows taskbar."""

    shell32 = WinDLL("shell32", use_last_error=True)
    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [LPCWSTR]
    shell32.SetCurrentProcessExplicitAppUserModelID.restype = c_int
    shell32.SetCurrentProcessExplicitAppUserModelID(APPLICATION_ID)


def resolve_window_theme(preference: str | None) -> WindowTheme:
    """Resolve an application preference before the React theme bridge is available."""

    if preference == "light":
        return "light"
    if preference == "dark":
        return "dark"
    try:
        with OpenKey(HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            apps_use_light_theme, _ = QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return "dark"
    return "light" if bool(apps_use_light_theme) else "dark"


def _window_handle(window: str | Any) -> tuple[Any, HWND]:
    user32 = WinDLL("user32", use_last_error=True)
    if not isinstance(window, str):
        native_window = getattr(window, "native", None)
        if native_window is not None:
            return user32, HWND(native_window.Handle.ToInt64())
    user32.FindWindowW.argtypes = [LPCWSTR, LPCWSTR]
    user32.FindWindowW.restype = HWND
    return user32, user32.FindWindowW(None, window)


def apply_window_theme(window: str | Any, theme: str) -> None:
    """Match the native caption to the resolved application theme."""

    _, window_handle = _window_handle(window)
    if not window_handle:
        return

    dark = theme != "light"
    caption = (13, 13, 13) if dark else (253, 254, 255)
    border = (37, 37, 37) if dark else (235, 239, 241)
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
    window: str | Any,
    icon_path: Path,
    caption_icon_path: Path,
    theme: WindowTheme = "dark",
) -> None:
    """Apply taskbar identity while leaving the native caption visually quiet."""

    user32, window_handle = _window_handle(window)
    user32.LoadImageW.argtypes = [c_void_p, LPCWSTR, UINT, c_int, c_int, UINT]
    user32.LoadImageW.restype = c_void_p
    user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    user32.SendMessageW.restype = LPARAM

    if not window_handle:
        return

    apply_window_theme(window, theme)

    native_window = getattr(window, "native", None) if not isinstance(window, str) else None
    if native_window is not None:
        from System import Action  # type: ignore[import-not-found]
        from System.Drawing import Icon  # type: ignore[import-not-found]

        def set_form_icon() -> None:
            native_window.Icon = Icon(str(icon_path))

        if bool(native_window.InvokeRequired):
            native_window.Invoke(Action(set_form_icon))
        else:
            set_form_icon()

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


def configure_splash_window(window: Any) -> None:
    """Use native corners and keep the temporary splash out of the taskbar."""

    user32, window_handle = _window_handle(window)
    if not window_handle:
        return

    user32.GetWindowLongPtrW.argtypes = [HWND, c_int]
    user32.GetWindowLongPtrW.restype = c_void_p
    user32.SetWindowLongPtrW.argtypes = [HWND, c_int, c_void_p]
    user32.SetWindowLongPtrW.restype = c_void_p
    extended_style = int(user32.GetWindowLongPtrW(window_handle, GWL_EXSTYLE) or 0)
    user32.SetWindowLongPtrW(
        window_handle,
        GWL_EXSTYLE,
        c_void_p((extended_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW),
    )
    user32.SetWindowPos(
        window_handle,
        None,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
    )

    corner_preference = c_int(DWMWCP_ROUND)
    border_colour = c_int(DWMWA_COLOR_NONE)
    dwmapi = WinDLL("dwmapi", use_last_error=True)
    dwmapi.DwmSetWindowAttribute.argtypes = [HWND, UINT, c_void_p, UINT]
    dwmapi.DwmSetWindowAttribute.restype = c_int
    for attribute, value in (
        (DWMWA_WINDOW_CORNER_PREFERENCE, corner_preference),
        (DWMWA_BORDER_COLOR, border_colour),
    ):
        dwmapi.DwmSetWindowAttribute(
            window_handle,
            attribute,
            byref(value),
            sizeof(value),
        )
