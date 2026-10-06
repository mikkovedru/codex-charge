from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

root = Path(SPECPATH).parent
# Build with system Python's GTK/XApp bindings (see scripts/build_linux.sh).
datas, binaries, hiddenimports = collect_all("pystray")
datas += collect_data_files("codex_charge")
for directory in (Path("/usr/lib/gtk-3.0/modules"), *Path("/usr/lib").glob("*-linux-gnu/gtk-3.0/modules")):
    binaries += [(str(p), "lib/gtk-3.0/modules") for p in directory.glob("*.so")]
a = Analysis([str(root / "scripts/entry_tray.py")], pathex=[str(root)],
             datas=datas, binaries=binaries, hiddenimports=hiddenimports + ["gi.repository.XApp", "gi._gi_cairo", "cairo"],
             hookspath=[str(root / "scripts/hooks")],
             # cairo.get_include() uses pkg_resources only when compiling extensions.
             # Do not pull Mint's distro setuptools into the frozen runtime.
             excludes=["numpy", "pytest", "pkg_resources"],
             hooksconfig={"gi": {"icons": [], "themes": [], "languages": ["en", "zh"]}})
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="codex-charge-tray", console=False)
