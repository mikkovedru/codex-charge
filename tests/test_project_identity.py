"""Upgrade the project identity without losing preferences or duplicating startup."""
import json
import stat
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import distribution
from pathlib import Path

import pytest

from recharge_ai_task import _migration, autostart, config, i18n


def legacy_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda _: tmp_path))
    monkeypatch.delenv('RECHARGE_AI_TASK_CONFIG_DIR', raising=False)
    monkeypatch.delenv(_migration.LEGACY_ENVIRONMENT_PREFIX + '_CONFIG_DIR', raising=False)
    source = tmp_path / _migration.LEGACY_CONFIG_DIRECTORY / 'config.json'
    source.parent.mkdir()
    data = {'language':'zh', 'autostart':True, 'continue_prompt':'First line\n第二行',
            'desktop_targets':[{'kind':'thread','id':'chosen','title':'Selected',
                                'send_prompt':False,'send_goal':True}]}
    source.write_bytes(json.dumps(data,ensure_ascii=False,indent=2).encode())
    return source


def test_first_launch_imports_every_preference_and_preserves_original(tmp_path, monkeypatch):
    source = legacy_home(tmp_path,monkeypatch)
    original = source.read_bytes()
    loaded = config.AppConfig.load()
    assert loaded.language == 'zh' and loaded.autostart
    assert loaded.continue_prompt == 'First line\n第二行'
    assert loaded.targets()[0].signal_actions() == (False,True)
    destination = tmp_path / '.recharge-ai-task' / 'config.json'
    assert destination.read_bytes() == source.read_bytes() == original
    if config.os.name != 'nt': assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    i18n.set_locale('en')


def test_concurrent_first_launch_publishes_one_complete_configuration(tmp_path, monkeypatch):
    source = legacy_home(tmp_path,monkeypatch)
    root = tmp_path / '.recharge-ai-task';root.mkdir()
    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(lambda _: _migration.import_settings(root),range(24)))
    assert (root/'config.json').read_bytes() == source.read_bytes()
    assert not list(root.glob('*.tmp'))


def test_existing_new_settings_win_over_old_settings(tmp_path, monkeypatch):
    source = legacy_home(tmp_path,monkeypatch)
    destination = tmp_path / '.recharge-ai-task' / 'config.json'
    destination.parent.mkdir();destination.write_text('{"continue_prompt":"New preference"}')
    assert config.AppConfig.load().continue_prompt == 'New preference'
    assert source.read_bytes() != destination.read_bytes()


def test_explicit_config_directory_stays_isolated(tmp_path, monkeypatch):
    source = legacy_home(tmp_path,monkeypatch)
    root = tmp_path / 'isolated'
    monkeypatch.setenv('RECHARGE_AI_TASK_CONFIG_DIR',str(root))
    assert config.config_dir() == root
    assert not (root/'config.json').exists() and source.exists()


def test_new_environment_variables_override_upgrade_fallbacks(tmp_path, monkeypatch):
    monkeypatch.delenv('RECHARGE_AI_TASK_CONFIG_DIR')
    old = _migration.LEGACY_ENVIRONMENT_PREFIX
    monkeypatch.setenv(old+'_CONFIG_DIR',str(tmp_path/'old-explicit'))
    assert config.config_dir() == tmp_path/'old-explicit'
    monkeypatch.setenv('RECHARGE_AI_TASK_CONFIG_DIR',str(tmp_path/'new-explicit'))
    assert config.config_dir() == tmp_path/'new-explicit'
    monkeypatch.setenv(old+'_LANG','zh')
    monkeypatch.delenv('RECHARGE_AI_TASK_LANG',raising=False)
    assert i18n.init_locale_from_env() == 'zh'
    monkeypatch.setenv('RECHARGE_AI_TASK_LANG','en')
    assert i18n.init_locale_from_env() == 'en'


@pytest.mark.parametrize('platform,suffix',[('linux','.desktop'),('win32','.bat')])
def test_startup_upgrade_leaves_exactly_one_named_registration(tmp_path,monkeypatch,platform,suffix):
    monkeypatch.setattr(autostart.sys,'platform',platform)
    target = tmp_path / ('recharge-ai-task-tray'+suffix)
    monkeypatch.setattr(autostart,'autostart_target',lambda:target)
    legacy = tmp_path / (_migration.LEGACY_TRAY_NAME+suffix)
    legacy.write_text('[Desktop Entry]\nX-GNOME-Autostart-enabled=true\n')
    assert autostart.is_autostart_enabled()
    autostart.sync_autostart(True)
    assert target.exists() and not legacy.exists()
    assert 'recharge_ai_task.tray' in target.read_text() and '--autostart' in target.read_text()
    if platform=='linux': assert 'Name=Recharge AI-task' in target.read_text()
    autostart.set_autostart(False)
    assert not target.exists() and not autostart.is_autostart_enabled()


def test_disabled_legacy_startup_stays_disabled(tmp_path,monkeypatch):
    monkeypatch.setattr(autostart.sys,'platform','linux')
    target = tmp_path / 'recharge-ai-task-tray.desktop'
    legacy = tmp_path / (_migration.LEGACY_TRAY_NAME+'.desktop')
    monkeypatch.setattr(autostart,'autostart_target',lambda:target)
    legacy.write_text('[Desktop Entry]\nHidden=true\n')
    assert not autostart.is_autostart_enabled()
    autostart.sync_autostart(False)
    assert not target.exists() and not legacy.exists()


def test_failed_startup_replacement_keeps_old_registration(tmp_path,monkeypatch):
    monkeypatch.setattr(autostart.sys,'platform','linux')
    target=tmp_path/'recharge-ai-task-tray.desktop'
    legacy=tmp_path/(_migration.LEGACY_TRAY_NAME+'.desktop')
    legacy.write_text('[Desktop Entry]\nX-GNOME-Autostart-enabled=true\n')
    monkeypatch.setattr(autostart,'autostart_target',lambda:target)
    original=Path.write_text
    def fail(self,*args,**kwargs):
        if self==target: raise OSError('Read-only startup directory')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(OSError): autostart.set_autostart(True)
    assert legacy.exists() and autostart.is_autostart_enabled()


def test_distribution_and_commands_use_new_identity():
    package=distribution('recharge-ai-task')
    assert package.metadata['Name']=='recharge-ai-task'
    assert {e.name:e.value for e in package.entry_points} == {
        'recharge-ai-task':'recharge_ai_task.cli:main',
        'recharge-ai-task-gui':'recharge_ai_task.gui:main',
        'recharge-ai-task-tray':'recharge_ai_task.tray:main',
        'recharge-ai-task-configure':'recharge_ai_task.configure:main'}
