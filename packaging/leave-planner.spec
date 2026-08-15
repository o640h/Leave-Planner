# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).parent
backend_root = project_root / "backend"
source_root = backend_root / "src"
frontend_root = project_root / "frontend"

entry_point = source_root / "desktop.py"
application_icon = source_root / "desktop_shell" / "assets" / "leave-planner.ico"

datas = [
    (str(frontend_root / "dist"), "frontend/dist"),
    (str(backend_root / "migrations"), "migrations"),
    (str(backend_root / "alembic.ini"), "."),
    (
        str(source_root / "desktop_shell" / "assets"),
        "desktop_shell/assets",
    ),
]

analysis = Analysis(
    [str(entry_point)],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("alembic"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Leave Planner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(application_icon),
)

application = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Leave Planner",
)