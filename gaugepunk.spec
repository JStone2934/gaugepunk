# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for GaugePunk tray app (Windows).
#
# 构建: pyinstaller gaugepunk.spec --clean --noconfirm
# 产物: dist/GaugePunk.exe (单文件, ~30-50MB)

from pathlib import Path

# spec 里 __file__ 不可用, 直接用 SPECPATH
ROOT = Path(SPECPATH)  # noqa: F821

a = Analysis(
    [str(ROOT / "host" / "tray.py")],
    pathex=[str(ROOT / "host")],
    binaries=[],
    datas=[
        (str(ROOT / "host" / "assets" / "gaugepunk.ico"), "host/assets"),
        (str(ROOT / "host" / "config.yaml"), "host"),
    ],
    hiddenimports=[
        "pystray._win32",
        "PIL.Image",
        "PIL.ImageDraw",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pydoc",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GaugePunk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "host" / "assets" / "gaugepunk.ico"),
)
