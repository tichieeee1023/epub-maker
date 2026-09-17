import os
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


# Tcl/Tk cannot resolve a Unicode Windows user-profile path in this build
# environment. Stage the runtime under the ASCII-only project path before
# PyInstaller's tkinter hook inspects it.
tcl_source = Path(sys.base_prefix) / "tcl"
tcl_stage = Path(SPECPATH) / "build" / "tcl-tk"
tcl_library = next(tcl_source.glob("tcl[0-9].[0-9]"))
tk_library = next(tcl_source.glob("tk[0-9].[0-9]"))
shutil.copytree(tcl_library, tcl_stage / tcl_library.name, dirs_exist_ok=True)
shutil.copytree(tk_library, tcl_stage / tk_library.name, dirs_exist_ok=True)
os.environ["TCL_LIBRARY"] = str(tcl_stage / tcl_library.name)
os.environ["TK_LIBRARY"] = str(tcl_stage / tk_library.name)


datas = collect_data_files("customtkinter")
datas += [
    ("styles", "styles"),
    ("templates", "templates"),
]

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    name="EPUB Maker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
