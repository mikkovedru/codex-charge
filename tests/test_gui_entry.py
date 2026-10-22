"""Desktop dispatch, standalone GUI startup and legacy launcher compatibility."""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from recharge_ai_task import cli, gui, desktop_launch as launcher


def test_root_help_lists_gui_and_tray_commands(capsys):
    assert cli.main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "gui" in output and "targets --gui" in output
    assert output.startswith("usage: recharge-ai-task-cli ")
    assert "tray" in output and "--tray" in output


@pytest.mark.parametrize("command,args", [(["gui"], []), (["targets", "--gui"], []),
    (["tray"], ["--tray"]), (["gui", "--tray"], ["--tray"])])
def test_cli_desktop_commands_skip_terminal_setup(monkeypatch, command, args):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", False, raising=False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "run_configure", lambda: pytest.fail("Asked for terminal configuration"))
    calls = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda command: calls.append(command) or 0)
    assert cli.main(command) == 0
    assert calls == [[gui.sys.executable, "-m", "recharge_ai_task.gui", *args]]


def test_frozen_cli_uses_the_combined_desktop_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(gui.sys, "executable", str(tmp_path / "recharge-ai-task-cli"))
    desktop = tmp_path / "recharge-ai-task"
    desktop.touch()
    calls = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda args: calls.append(args) or 0)
    assert launcher.launch([], tray=True) == 0
    assert calls == [[str(desktop), "--tray"]]


def test_missing_desktop_companion_is_clear_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(gui.sys, "executable", str(tmp_path / "recharge-ai-task-cli"))
    assert launcher.launch([]) == 1
    assert "Missing desktop executable" in capsys.readouterr().err


@pytest.mark.parametrize("args,forwarded", [([], ["--targets"]), (["gui"], ["--targets"]), (["tray"], []), (["--tray"], []),
    (["--settings"], ["--settings"]), (["--targets"], ["--targets"]),
    (["--autostart"], ["--autostart"]), (["--tray", "--autostart"], ["--autostart"])])
def test_combined_desktop_runs_in_process_without_companion(monkeypatch, tmp_path, args, forwarded):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(gui.sys, "executable", str(tmp_path / "recharge-ai-task"))
    calls = []
    monkeypatch.setitem(sys.modules, "recharge_ai_task.tray", SimpleNamespace(main=lambda options: calls.append(options) or 0))
    monkeypatch.setattr(launcher.subprocess, "call", lambda *a: pytest.fail("Started a second desktop executable"))
    assert gui.main(args) == 0
    assert calls == [forwarded]
    assert list(tmp_path.iterdir()) == []


def test_windows_desktop_defaults_to_tray(monkeypatch):
    monkeypatch.setattr(gui.sys, "platform", "win32")
    calls = []
    monkeypatch.setitem(sys.modules, "recharge_ai_task.tray", SimpleNamespace(main=lambda options: calls.append(options) or 0))
    assert gui.main([]) == 0
    assert calls == [[]]


@pytest.mark.parametrize("args", [["--tray", "--settings"], ["--autostart", "--settings"], ["--unknown"]])
def test_bad_desktop_arguments_fail_before_startup(args):
    with pytest.raises(SystemExit) as exc:
        gui.main(args)
    assert exc.value.code == 2


def test_desktop_help_does_not_import_graphical_runtime(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "recharge_ai_task.tray", None)
    with pytest.raises(SystemExit) as exc:
        gui.main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert output.startswith("usage: recharge-ai-task ")
    assert "--tray" in output and "recharge-ai-task-cli" in output


@pytest.mark.skipif(sys.platform != "linux", reason="Linux compatibility launcher")
@pytest.mark.parametrize("script,alias", [("launch_tray.sh", "recharge-ai-task-tray"), ("launch_gui.sh", "recharge-ai-task-gui")])
@pytest.mark.parametrize("args,expected", [([], ["--tray"]), (["--autostart"], ["--tray", "--autostart"]),
    (["--targets"], ["--targets"]), (["--settings"], ["--settings"]),
    (["--resume-goal-ui"], ["--resume-goal-ui"])])
def test_legacy_launcher_follows_symlink_and_preserves_arguments(tmp_path, args, expected, script, alias):
    import json
    package = tmp_path / "release folder"
    package.mkdir()
    desktop = package / "recharge-ai-task"
    desktop.write_text("#!/bin/sh\nexec " + sys.executable + " -c 'import json,sys; print(json.dumps(sys.argv[1:])); sys.exit(7)' \"$@\"\n")
    desktop.chmod(0o755)
    wrapper = package / alias
    wrapper.write_bytes((Path(__file__).resolve().parents[1] / "scripts" / script).read_bytes())
    wrapper.chmod(0o755)
    link = tmp_path / alias
    link.symlink_to(wrapper)
    result = subprocess.run([str(link), *args],cwd="/tmp",capture_output=True,text=True)
    assert result.returncode == 7, result.stderr
    assert json.loads(result.stdout) == (args if script == "launch_gui.sh" else expected)


def test_primary_package_module_uses_desktop_entry_point(monkeypatch):
    import runpy
    calls = []
    monkeypatch.setattr(gui, "main", lambda: calls.append("desktop") or 0)
    monkeypatch.setattr(sys, "argv", ["recharge-ai-task"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("recharge_ai_task", run_name="__main__")
    assert exc.value.code == 0 and calls == ["desktop"]


def test_primary_desktop_rejects_cli_commands_and_points_to_cli(capsys):
    with pytest.raises(SystemExit) as exc:
        gui.main(["quota"])
    assert exc.value.code == 2
    # The desktop help tells users which executable owns terminal commands.
    with pytest.raises(SystemExit):
        gui.main(["--help"])
    assert "recharge-ai-task-cli" in capsys.readouterr().out
