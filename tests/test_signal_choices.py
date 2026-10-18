"""Per-recipient action persistence, migration and quota-reset delivery."""
from dataclasses import replace
import pytest
from recharge_ai_task.config import AppConfig
from recharge_ai_task.targets import Target
from recharge_ai_task import watch
from recharge_ai_task.target_delivery import DeliveryResult
from recharge_ai_task.quota import Quota, RateWindow


@pytest.mark.parametrize('legacy_goal', [False, True])
def test_legacy_saved_selection_migrates_without_losing_recipients(legacy_goal):
    chat = Target('thread', 'chat', 'Chat')
    window = Target('window', 'window', 'Window')
    AppConfig(goal_mode=legacy_goal, desktop_targets=[chat.to_dict(), window.to_dict()]).save()
    saved = AppConfig.load().targets()
    assert {t.id: t.signal_actions() for t in saved} == {'chat': (True, legacy_goal), 'window': (True, False)}


def test_explicit_actions_override_legacy_setting_and_roundtrip():
    selected = [Target('thread', name, name, send_prompt=prompt, send_goal=goal)
        for name, prompt, goal in [('prompt', True, False), ('goal', False, True), ('both', True, True), ('off', False, False)]]
    AppConfig(goal_mode=True, desktop_targets=[t.to_dict() for t in selected]).save()
    assert AppConfig.load().targets() == selected[:3]
    AppConfig(goal_mode=False, desktop_targets=[t.to_dict() for t in selected]).save()
    assert AppConfig.load().targets() == selected[:3]


def test_watch_uses_each_recipient_actions_and_retries_only_failed_target(monkeypatch):
    targets = tuple(Target('thread', name, name, send_prompt=prompt, send_goal=goal)
        for name, prompt, goal in [('prompt', True, False), ('goal', False, True), ('both', True, True), ('off', False, False)])
    blocked = Quota('test', RateWindow(100, 300, 0), None, True)
    available = replace(blocked, primary=RateWindow(0, 300, 9999999999), rate_limit_reached=False)
    snapshots = iter([blocked, available, available])
    monkeypatch.setattr(watch, 'discover_codex', lambda _: 'offline')
    monkeypatch.setattr(watch, 'fetch_quota', lambda _: next(snapshots, available))
    calls, waits = [], []
    def send(targets, text, **kwargs):
        target = targets[0]
        calls.append((target.id, target.signal_actions(), text, kwargs.get('manual', False)))
        return [DeliveryResult(target, target.id != 'both' or len(calls) > 3, 'fixture')]
    monkeypatch.setattr(watch, 'send_signals', send)
    class Stop:
        def is_set(self): return len(waits) >= 3
        def wait(self, seconds): waits.append(seconds)
    watch.run_desktop_watch(watch.WatchConfig(desktop_targets=targets, goal_mode=False, grace_seconds=0), Stop())
    assert calls == [('prompt', (True, False), 'Continue', False), ('goal', (False, True), 'Continue', False),
                     ('both', (True, True), 'Continue', False), ('both', (True, True), 'Continue', False)]


def test_startup_only_checks_recipients_with_goal_enabled(monkeypatch):
    targets = tuple(Target('thread', name, name, send_prompt=prompt, send_goal=goal)
        for name, prompt, goal in [('prompt', True, False), ('goal', False, True)])
    monkeypatch.setattr(watch, 'discover_codex', lambda _: 'offline')
    monkeypatch.setattr(watch, 'fetch_quota', lambda _: Quota('test', RateWindow(0, 300, 0), None, False))
    checked, sent, waits = [], [], []
    def candidates(targets, **kwargs):
        checked.extend(t.id for t in targets)
        return {targets[0].key}, []
    monkeypatch.setattr(watch, 'quota_stopped_targets', candidates)
    monkeypatch.setattr(watch, 'send_signals', lambda targets, *a, **k: sent.append(targets[0].id) or [DeliveryResult(targets[0], True, 'fixture')])
    class Stop:
        def is_set(self): return bool(waits)
        def wait(self, seconds): waits.append(seconds)
    watch.run_desktop_watch(watch.WatchConfig(desktop_targets=targets, grace_seconds=0), Stop())
    assert checked == ['goal'] and sent == ['goal']


def test_cli_reselection_preserves_existing_signal_choices(monkeypatch, capsys):
    from recharge_ai_task import cli, targets
    saved = Target('thread', 'chosen', 'Old title', send_prompt=False, send_goal=True)
    AppConfig(desktop_targets=[saved.to_dict()]).save()
    monkeypatch.setattr(targets, 'discover_targets', lambda: targets.Inventory([replace(saved, title='New title')]))
    assert cli.main(['targets', '--select', 'chosen', '--json']) == 0
    assert AppConfig.load().targets() == [replace(saved, title='New title')]


def test_watch_restart_preserves_successes_and_retries_confirmed_failure(monkeypatch):
    targets = tuple(Target('thread', name, name, send_prompt=True, send_goal=False) for name in ('a', 'b'))
    state = watch.WatchState(startup_checked=True, delivered={targets[0].key},
                             seen_resets={(300, 0)}, pending=True)
    monkeypatch.setattr(watch, 'discover_codex', lambda _: 'offline')
    monkeypatch.setattr(watch, 'fetch_quota', lambda _: Quota('test', RateWindow(0, 300, 0), None, False))
    calls = []
    def send(targets, text, **kwargs):
        calls.append((targets[0].id, text))
        return [DeliveryResult(targets[0], len(calls) == 2, 'fixture')]
    monkeypatch.setattr(watch, 'send_signals', send)
    class Stop:
        stopped = False
        def is_set(self): return self.stopped
        def wait(self, seconds): self.stopped = True
    watch.run_desktop_watch(watch.WatchConfig(desktop_targets=targets, continue_prompt='Old', state=state), Stop())
    assert state.pending and state.delivered == {targets[0].key}
    watch.run_desktop_watch(watch.WatchConfig(desktop_targets=targets, continue_prompt='New', state=state), Stop())
    assert calls == [('b', 'Old'), ('b', 'New')]
    assert not state.pending and state.delivered == {target.key for target in targets}
