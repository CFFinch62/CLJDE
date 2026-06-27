# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CLJDE.

Build with: pyinstaller build/CLJDE.spec
Output: dist/CLJDE (standalone executable)
"""

import os

# Relative paths in a spec are resolved against the spec's directory, so
# anchor everything to the project root (the parent of build/) instead.
PROJECT_ROOT = os.path.dirname(SPECPATH)

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, "cljde", "resources"), "cljde/resources"),
        (os.path.join(PROJECT_ROOT, "images"), "images"),
    ],
    hiddenimports=[
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CLJDE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(PROJECT_ROOT, "images", "cljde-icon.svg")],
)

# For development: use one-dir mode
# Comment out the EXE above and uncomment below for faster iteration

# exe = EXE(
#     pyz,
#     a.scripts,
#     [],
#     exclude_binaries=True,
#     name="CLJDE",
#     debug=False,
#     bootloader_ignore_signals=False,
#     strip=False,
#     upx=True,
#     console=False,
# )
#
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name="CLJDE",
# )
