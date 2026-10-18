"""English-only messages, setup and upgrades from old language preferences."""
import json

import pytest

from recharge_ai_task import cli, config, configure
from recharge_ai_task._migration import LEGACY_CONTINUE_PROMPT
from recharge_ai_task.i18n import t
from recharge_ai_task.watch import WatchConfig
from recharge_ai_task.wrapper import WrapperConfig


def test_messages_stay_english_with_old_environment_preferences(monkeypatch):
    for name in ("LANG", "RECHARGE_AI_TASK_LANG", "CODEX_CHARGE_LANG"):
        monkeypatch.setenv(name, "zh_CN.UTF-8")
    assert t("app.name") == "Recharge AI-task"
    assert t("tray.exit") == "Exit"
    assert t("configure.saved", path="example.json") == "Configuration saved to example.json"
    assert t("unknown.message") == "unknown.message"


@pytest.mark.parametrize("prompt", [None, LEGACY_CONTINUE_PROMPT, "My custom prompt\n\u7b2c\u4e8c\u884c"])
def test_old_settings_use_english_without_losing_recipient_or_custom_prompt(prompt):
    data = {"language":"zh", "autostart":True, "desktop_targets":[{"kind":"thread", "id":"chosen", "title":"Chosen", "send_prompt":True, "send_goal":False}]}
    if prompt is not None:
        data["continue_prompt"] = prompt
    config.config_path().write_text(json.dumps(data))
    loaded = config.AppConfig.load()
    assert loaded.continue_prompt == ("Continue" if prompt in (None, LEGACY_CONTINUE_PROMPT) else prompt)
    assert loaded.autostart and loaded.targets()[0].id == "chosen"
    assert not hasattr(loaded, "language")
    loaded.save()
    saved = json.loads(config.config_path().read_text())
    assert "language" not in saved and saved["continue_prompt"] == loaded.continue_prompt
    assert saved["desktop_targets"] == data["desktop_targets"]


def test_defaults_are_english_in_cli_and_desktop_modes():
    assert config.AppConfig().continue_prompt == WatchConfig().continue_prompt == WrapperConfig().continue_prompt == "Continue"


def test_setup_has_no_language_questions(monkeypatch, capsys):
    prompts = []
    def answer(prompt):
        prompts.append(prompt)
        return ""
    monkeypatch.setattr("builtins.input", answer)
    result = configure.run_configure()
    assert result.continue_prompt == "Continue"
    assert len(prompts) == 4
    assert all("Language" not in prompt for prompt in prompts)
    assert "Welcome to Recharge AI-task setup." in capsys.readouterr().out


def test_configure_help_removes_language_option(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["configure", "--help"])
    assert exc.value.code == 0
    assert "--lang" not in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        cli.main(["configure", "--lang", "zh"])
    assert exc.value.code == 2
