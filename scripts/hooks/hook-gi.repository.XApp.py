from PyInstaller.utils.hooks.gi import GiModuleInfo

module = GiModuleInfo("XApp", "1.0")
if module.available:
    binaries, datas, hiddenimports = module.collect_typelib_data()
