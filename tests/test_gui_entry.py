"""CLI help and GUI launch paths without opening a real window."""
import pytest
from codex_charge import cli, gui


def test_root_help_lists_both_gui_commands(capsys):
    assert cli.main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "gui" in output and "targets --gui" in output
    assert "codex-charge-gui" in output


@pytest.mark.parametrize("command", [["gui"], ["targets", "--gui"]])
def test_gui_aliases_launch_dashboard_without_configuration(monkeypatch, command):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", False, raising=False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "run_configure", lambda: pytest.fail("Asked for terminal configuration"))
    calls = []
    monkeypatch.setattr(gui.subprocess, "call", lambda args: calls.append(args) or 0)
    assert cli.main(command) == 0
    assert calls == [[gui.sys.executable, "-m", "codex_charge.tray", "--targets"]]


def test_dedicated_frozen_launcher_resolves_companion(monkeypatch, tmp_path):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(gui.sys, "executable", str(tmp_path / "codex-charge-gui"))
    (tmp_path / "codex-charge-tray").touch()
    calls = []
    monkeypatch.setattr(gui.subprocess, "call", lambda args: calls.append(args) or 0)
    assert gui.main([]) == 0
    assert calls == [[str(tmp_path / "codex-charge-tray"), "--targets"]]


def test_missing_gui_companion_is_clear_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gui.sys, "platform", "linux")
    monkeypatch.setattr(gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(gui.sys, "executable", str(tmp_path / "codex-charge-gui"))
    assert gui.main([]) == 1
    assert "Missing companion" in capsys.readouterr().err
