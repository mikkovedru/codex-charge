"""Display semantics shared by status cells, tooltips, and the message log."""

COLORS = {"success": "#198038", "warning": "#b38f00", "error": "#c62828"}
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
    description = " ".join(states.get(part, ("warning", "This state is not recognized by this version."))[1]
                           for part in value.split(" / "))
    legend = "\n".join(f"{name}: {text}" for name, (_, text) in states.items())
    return f"{value}: {description}\n\n{'Goal' if goal else 'Task'} statuses\n{legend}"
