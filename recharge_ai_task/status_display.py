"""Display semantics shared by status cells, tooltips, and the message log."""

from math import ceil

COLORS = {"success": "#198038", "warning": "#b38f00", "error": "#c62828"}


def watch_check_summary(runtime, now):
    """Describe the worker's next check without predicting task recovery."""
    if runtime is None:
        return "Unavailable", "The tray could not be reached."
    if runtime.get("stopping"):
        return "Stopping…", "Pending monitoring is being stopped."
    if runtime.get("restarting"):
        return "Updating…", "Applying saved monitoring settings."
    if runtime.get("watch_error"):
        return "Needs attention", "See the activity messages below."
    if runtime.get("watch_pause_reason"):
        return "Waiting", "Choose valid recipients and signal settings."
    if runtime.get("cli_running"):
        return "CLI mode", "Quota recovery is managed in the terminal."
    if not runtime.get("desktop_watch"):
        return "—", "Desktop monitoring is off."
    progress = runtime.get("watch_progress") or {}
    phase = progress.get("phase")
    if phase == "checking_quota":
        return "Checking…", "Reading current quota availability."
    if phase == "delivering":
        return "Sending…", "Delivering the selected signals."
    reasons = {"waiting_quota": "Waiting for quota to become available.",
               "quota_unavailable": "Quota could not be read; checking again.",
               "grace_period": "Quota is available; retaining the grace period.",
               "retry_pending": "A confirmed delivery failure is waiting for retry.",
               "monitoring": "Watching for quota changes."}
    due = progress.get("next_check_at")
    if phase not in reasons or not isinstance(due, (int, float)):
        return "Waiting…", "Waiting for a monitoring update."
    seconds = max(0, ceil(due - now))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    countdown = f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"
    return (f"In {countdown}" if due > now else "Due now"), reasons[phase]


TASK_STATES = {
    "Active": ("success", "Codex is working on a turn."),
    "Running": ("success", "Codex is working on a turn."),
    "Waiting for approval": ("warning", "A turn is active but needs your approval before continuing."),
    "Waiting for input": ("warning", "A turn is active but needs your reply before continuing."),
    "Idle": ("normal", "No turn is currently running."),
    "Error": ("error", "Codex reports a runtime error for this task."),
    "Not loaded": ("normal", "The saved chat is not loaded in the queried backend."),
    "Unavailable": ("warning", "The current state could not be read; this does not mean idle."),
}
GOAL_STATES = {
    "Active": ("success", "The goal is enabled and may continue automatically; check Task status for current activity."),
    "Paused": ("warning", "The goal is intentionally paused. Manual Goal signals may resume it; quota recovery leaves it paused."),
    "Usage limited": ("warning", "The goal stopped because account quota was exhausted. Goal signals can resume it when quota recovers."),
    "Budget limited": ("error", "The goal reached its own token budget. A continuation signal does not override this limit."),
    "Blocked": ("error", "The goal cannot make progress without user input or an external change."),
    "Complete": ("normal", "Codex marked the goal achieved. A continuation signal does not reopen it."),
    "No goal": ("normal", "This chat has no saved goal."),
    "Unavailable": ("warning", "The goal state could not be read; this does not mean there is no goal."),
}


def status_level(value, *, goal=False):
    states = GOAL_STATES if goal else TASK_STATES
    # A task may simultaneously need approval and input.
    parts = value.split(" / ")
    levels = [states.get(part, ("warning", ""))[0] for part in parts]
    return next((level for level in ("error", "warning", "success") if level in levels), "normal")


def status_tooltip(value, *, goal=False):
    states = GOAL_STATES if goal else TASK_STATES
    legend = "\n".join(f"{name}: {text}" for name, (_, text) in states.items())
    return f"{'Goal' if goal else 'Task'} statuses\n{legend}"
