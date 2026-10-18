"""CLI help and GUI launch paths without opening a real window."""
import pytest
from recharge_ai_task import cli, gui


def test_root_help_lists_both_gui_commands(capsys):
    assert cli.main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "gui" in output and "targets --gui" in output
    assert "recharge-ai-task-gui" in output


@pytest.mark.parametrize("command", [["gui"], ["targets", "--gui"]])
def test_gui_aliases_launch_dashboard_without_configuration(monkeypatch, command):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", False, raising=False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "run_configure", lambda: pytest.fail("Asked for terminal configuration"))
    calls = []
    monkeypatch.setattr(gui.subprocess, "call", lambda args: calls.append(args) or 0)
    assert cli.main(command) == 0
    assert calls == [[gui.sys.executable, "-m", "recharge_ai_task.tray", "--targets"]]


def test_dedicated_frozen_launcher_resolves_companion(monkeypatch, tmp_path):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(gui.sys, "executable", str(tmp_path / "recharge-ai-task-gui"))
    (tmp_path / "recharge-ai-task-tray").touch()
    calls = []
    monkeypatch.setattr(gui.subprocess, "call", lambda args: calls.append(args) or 0)
    assert gui.main([]) == 0
    assert calls == [[str(tmp_path / "recharge-ai-task-tray"), "--targets"]]


def test_missing_gui_companion_is_clear_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(gui.sys, "executable", str(tmp_path / "recharge-ai-task-gui"))
    assert gui.main([]) == 1
    assert "Missing companion" in capsys.readouterr().err
