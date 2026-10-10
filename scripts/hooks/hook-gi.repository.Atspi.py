"""Bundle the native accessibility typelib used by the Goal helper."""
from PyInstaller.utils.hooks.gi import GiModuleInfo

module_info = GiModuleInfo("Atspi", "2.0")
if module_info.available:
    binaries, datas, hiddenimports = module_info.collect_typelib_data()
