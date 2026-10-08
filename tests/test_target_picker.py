"""Opt-in GTK regression using synthetic targets and isolated settings."""
import os
import subprocess
import sys
import pytest


@pytest.mark.skipif(os.environ.get("CODEX_CHARGE_GUI_TESTS") != "1", reason="Requires Linux GTK and a display")
def test_picker_filters_selects_and_saves():
    result = subprocess.run([sys.executable, "-c", r'''
from codex_charge import target_ui
from codex_charge.targets import Inventory, Target
from codex_charge.config import AppConfig
from gi.repository import GLib, Gtk
alpha = Target("thread", "alpha", "Same title", instance="profile", deeplink="codex://threads/alpha")
beta = Target("thread", "beta", "Same title", instance="profile", deeplink="codex://threads/beta")
target_ui.discover_targets = lambda: Inventory([alpha, beta])
window = target_ui.TargetPicker()
window.show_all()
errors = []
def check():
    if window.busy:
        return True
    try:
        window.search.set_text("beta")
        window.filtered.refilter()
        assert len(window.filtered) == 1
        window._toggle(None, "0")
        assert list(window.selected.values()) == [beta]
        window.search.set_text("")
        window.filtered.refilter()
        window._toggle(None, "0")
        window.goal.set_active(False)
        window.signal.set_text("Continue")
        window.save()
        saved = AppConfig.load()
        assert {t.id for t in saved.targets()} == {"alpha", "beta"}
        assert saved.continue_prompt == "Continue"
        assert not saved.goal_mode
    except Exception as exc:
        errors.append(str(exc))
    finally:
        window.destroy()
    return False
GLib.timeout_add(100, check)
Gtk.main()
assert not errors, errors
'''], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "CRITICAL" not in result.stderr, result.stderr
