"""Tests for i18n."""

from recharge_ai_task.i18n import normalize_locale, set_locale, t


def test_normalize_locale() -> None:
    assert normalize_locale("zh-CN") == "zh"
    assert normalize_locale("en_US") == "en"
    assert normalize_locale(None) == "en"


def test_translate_en_zh() -> None:
    set_locale("en")
    assert "Recharge AI-task" in t("app.name")
    set_locale("zh")
    assert t("tray.exit") == "退出"
