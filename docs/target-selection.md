# Codex target discovery and delivery

The selector distinguishes **desktop windows** (X11 window ID + process ID)
from **Codex chats** (stable thread ID + Codex profile). Titles are labels, not
identities: two chats can have the same name, and several chats can use the same
window. Selection is explicit, supports several recipients, and survives restart.

## Research

The official [App Server reference](https://learn.chatgpt.com/docs/app-server)
documents `thread/list`, pagination, `thread/read`, and existing Unix WebSocket
control sockets. [Deep links](https://learn.chatgpt.com/docs/reference/commands#deep-links)
use `codex://threads/<thread-id>` to open existing local chats.

On this Mint installation, Codex CLI is 0.160.0 and the managed local daemon is
0.161.0. Connecting to its existing control socket can list saved chats, but
`thread/loaded/list` returns no loaded chats even while the desktop is actively
running them. Its `notLoaded` status is therefore not used as the desktop's
availability signal. Starting a second app-server to resume these chats would
not address the existing desktop owner.

The installed desktop code also exposes a private, per-user routing socket at
`$CODEX_HOME/ipc/ipc.sock`. Inspection and read-only probes established its
four-byte little-endian JSON frame length, initialization handshake, versioned
`thread-owner-discovery` request, and `thread-follower-start-turn` request. Owner
discovery identifies the exact existing desktop client for a thread. This is
private implementation detail, not an officially supported integration API.
It is isolated in `codex_ipc.py`, checks ownership and acknowledgments, and fails
with an error on incompatible versions. Chat delivery never falls back to typing
in an arbitrary window or resuming the chat in another server.

## Discovery

- Linux X11: enumerate managed windows through EWMH and match application class,
  rather than titles that could belong to browsers. Show title, XID, PID and display.
- Discover running same-user Codex profiles from their `CODEX_HOME` and existing
  daemon control sockets. Read only that environment field, not credentials.
- Query all pages of user chat metadata from existing daemons. Fall back to a
  read-only SQLite connection with schema checks. Archived chats and internal
  subagents are excluded. Titles prefer the saved user-facing `name`.
- Probe desktop ownership separately; show saved versus open chats and owner IDs.
- Preserve selected rows if a window or chat temporarily disappears. Delivery
  revalidates availability and identity instead of silently replacing a recipient.

This inventories locally available Codex chats and desktop windows. It does not
query account-wide ChatGPT conversation history or enumerate disconnected remote
hosts. Linux Wayland cannot use X11 window delivery. The GTK picker is for Linux;
the CLI inventory/selection also supports Windows window discovery. Thread
routing currently requires the Linux desktop's Unix socket.

## User flow

Open **Open Codex Charge…** in the tray, or run `codex-charge gui`, `codex-charge-gui`, or `codex-charge targets --gui`.
The root `codex-charge --help` lists both GUI command forms. A Linux release
contains the CLI, tray, and dedicated GUI launcher; keep them together.
All GUI launch commands start the tray too. Further launches reuse the same tray
and present its existing window, preserving the current view. Closing the window
keeps the tray and watch running. Double-click the icon to hide the visible
dashboard to the tray, or restore it with the current view intact. GUI launch
commands and **Open Codex Charge…** always show the dashboard. Right-click for
the tray menu, including **Exit** to quit.
Search by title, ID, project, PID or deep link. Enable **Prompt**, **Goal**, or both
for each recipient and edit the multiline prompt message. Newlines are preserved
when saving and sending. These changes save automatically for quota-reset
delivery. **Send signals** uses the current choices immediately.
Prompt sends only the message. Goal resumes natively and starts
continuation without a prompt. Both activates the goal first, then sends the
prompt. Window rows support Prompt only. **Open selected row** opens a chat
without sending.
Metadata columns can be resized and scrolled; hovering a row shows full values.

Successful automatic saves do not add a status line. Write failures remain
visible and retry while the window is open. Changes made by another picker are
reported without overwriting them during refresh. The **Start/Stop Desktop watch** button
controls the tray's actual worker. Its adjacent status has a green border when
On, a red border when Off, and a yellow border while Stopping. It updates every
two seconds. A stopping worker must finish before another starts. If the tray is absent, Start launches it.
Closing the picker leaves the tray and active watch running.

The list includes separate **Task status** and **Goal status** columns next to
its title. Status and target discovery refresh every 15 seconds without clearing
your choices; **Refresh** updates them immediately. Directly below the list,
**Refresh** appears on the left, followed by the last refresh time, with
**Copy link / ID** and **Open selected row** on the right. Below the multiline
prompt, the recipient summary shares a row with **Send signals** at the far
right. Search also matches both status columns and the project name.

**Project** and **Project path** sit between **Goal status** and **Kind**. Project
names come from read-only, schema-checked Codex project metadata, combining
native SQLite memberships with desktop assignments retained during migration.
Native names take precedence over old cached names; explicit chat membership is
used even when the working path has moved. Older releases use the desktop state
file. Unassigned chats and window recipients have no project name. Unsupported
or unreadable metadata produces a discovery warning, while paths remain visible.
Folder names are not substituted for custom names.

Task status reports **Running**, **Waiting for approval**, **Waiting for input**,
**Idle**, **Error**, or **Not loaded**. For an open local chat, a temporary,
owner-pinned observer reads the desktop's current runtime snapshot and detaches.
It never resumes the chat or starts a turn. Desktop state takes precedence over
the metadata daemon, which can report an active desktop chat as not loaded.
The private snapshot adapter currently supports version 11 and fails visibly if
it becomes incompatible. Only status fields are retained; conversation contents
and goal objectives are discarded.

Goal status reports **Active**, **Paused**, **Blocked**, **Usage limited**,
**Budget limited**, **Complete**, or **No goal**. A read-only, schema-checked
`goals_*.sqlite` query supplies persisted status for saved chats and is read again
after live snapshots. This keeps an older desktop cache from hiding native goal
updates made through another connection. Cached completed goals are shown when
no newer persisted goal exists. A missing or unsupported source
is **Unavailable**, rather than an inferred idle task or absent goal. Window
recipients show **Unavailable** because they do not identify a fixed chat.
Disconnected saved selections remain listed with unavailable statuses.
The public runtime and goal states are documented in the
[Codex App Server reference](https://learn.chatgpt.com/docs/app-server).

Task and goal cells are colored and explain the current state and all supported
states on hover. **Running** (active) is green; **Waiting for approval** and
**Waiting for input** are yellow; **Error** is red. **Idle** and **Not loaded**
use normal text, and **Unavailable** is yellow. A task can need both approval
and input simultaneously. **Active** is also accepted as a green display label.

For goals, **Active** is green, **Paused** and **Usage limited** are yellow,
**Budget limited** and **Blocked** are red, **No goal** uses normal text, and
**Unavailable** is yellow. **Complete** uses normal text preceded by a green
checkmark. Persisted `usage_limited` and `budget_limited` are displayed as
**Usage limited** and **Budget limited**.

The multi-line status area scrolls and retains recent messages, each prefixed
with the local date and time (`YYYY-MM-DD HH:MM:SS`). Warnings are
yellow, errors red, and signal sending/results green. Saving, startup toggles
and watch start/restart messages use the normal theme text color. Mixed sends
show each recipient's result in its own color, with a red summary for failures
or yellow for skipped actions. Long logs are bounded and new messages do not
move the scroll position while you are reading older diagnostics.

Live quota shows usage, local reset dates, and a countdown for each limit.
The 5-hour and weekly lines are colored independently: normal theme text below
85% used, yellow from 85%, and red at 100% or above.
Quota refreshes automatically every minute and can be refreshed manually; the
countdown updates every second. A failed refresh keeps the last known values
with their age and the error. Quota requests time out if Codex stops responding.

**Run at login** reports the operating system's startup registration; **This tray
started at login** reports whether this session came from the startup entry.
The entry launches the tray, without automatically starting Desktop watch.
Startup entries include `--autostart` so future launches can identify their
origin; enabled older entries are migrated when the updated tray starts.

**Settings…** opens a GTK editor for language, default mode, Codex CLI path and
arguments, reset grace, polling interval, and startup registration. The tray's
Settings menu opens this editor too. Prompt text and per-recipient signal choices remain visible
in the main window. Saved settings and recipients automatically restart an active watch after a
600 ms debounce. The previous worker finishes before its replacement starts;
quota-reset identities, accepted/uncertain recipients and pending retries survive
the restart. Prompt typing and checkbox changes coalesce into one update.
An empty selection or blank Prompt draft suspends the watch until settings become
valid. Stop cancels pending restarts; saving while Off does not start a watch.
Configuration is saved atomically.

On Linux, the picker and tray communicate through a private Codex Charge control
socket in the configuration directory. Only same-user clients are accepted,
the socket is mode `0600`, and a second tray cannot replace an active socket.
The dashboard controls a watch started by the tray; a separately launched
`codex-charge watch` process is managed in its own terminal.

CLI examples:

```bash
codex-charge targets --json
codex-charge targets --select THREAD_ID_1 --select THREAD_ID_2
codex-charge targets --clear
codex-charge watch
```

Use the full `key` from JSON output when an ID is ambiguous across profiles.
No selection means no automatic signal. Legacy first-title-match watch behavior
has been replaced; users must choose recipients once.

## Delivery and retries

For a chat, discover its owner and route the versioned request directly to that
client. If a saved chat has no owner, open its canonical deep link and wait for an
owner before sending. No model, permission or workspace changes are requested.
Ordinary signals are text input; this path does not emulate the composer's
slash-command UI handlers. Native goal recovery is a separate operation:

Each saved recipient carries independent `send_prompt` and `send_goal` flags.
The GUI no longer has a global goal-recovery toggle. Legacy selections migrate
using the old `goal_mode` value, which remains a CLI option. New CLI `--select`
recipients default to Prompt only; `targets --json` reports saved action choices.

For Goal, the adapter reads the selected chat's goal through the existing same-user
Codex daemon. Native `thread/goal/get` and `thread/goal/set` share persisted state
with the desktop even when that daemon has not loaded the chat. No objective,
budget or usage history is replaced. Activation is rechecked and verified before
continuation through the desktop's current owner. Goal-only uses a turn with an
empty input list, so no user prompt is added. With both choices enabled, verified
Goal activation is followed by one turn carrying the selected prompt.

Manual sends may activate paused goals even during an active prompt turn.
Goal-only changes the native goal state and lets that existing turn continue; it
does not submit another empty turn. Both still activates the goal before its
independently selected prompt. Activation verification allows usage to advance
during a running turn, but rejects accounting resets and budget changes. Automatic recovery leaves intentional
pauses alone. Goal actions skip missing, blocked, budget-limited, complete or
already-running goals during automatic recovery. When Prompt is also selected, skipped Goal actions are
reported and the independent Prompt still sends. Failed or uncertain Goal
activation prevents prompt fallback. Ambiguous continuation acknowledgement is
not retried automatically in the same reset. Window identities cannot identify
an individual goal, so their Goal checkbox is disabled.

This applies on every quota recovery, replacing the old once-per-watch first
message behavior. Starting a watch after quota has recovered also finds selected
usage-limited goals and recovers only those, after the grace period. Other chats
receive no startup signal. Failed startup checks retry while the watch runs.

A window recipient means the currently displayed chat and focused input in that
window. Keep its composer focused before using window delivery; chat ID targets
avoid this focus dependency. Window delivery validates the XID/PID and foreground
window before typing and submitting. Closing a window or reusing an ID causes a
failure. Desktop settings and conversation drafts are not cleared.

The watcher waits for every exhausted quota window (including the weekly
window), keeps the grace period, then checks fresh quota before sending. A passed
reset timestamp alone does not trigger delivery. Failed quota reads and a
remaining rate-limit flag postpone delivery.

The watcher tracks accepted recipients separately for each reset. Confirmed
failures retry every 30 seconds while quota is available; this pending delivery
survives the quota returning to normal. Confirmed successes are not resent within
that reset.
Native recovery rechecks the current goal on confirmed retries, so an already
activated goal is not activated again. A timeout or connection loss after native
activation or turn submission is **uncertain**, so it is not automatically
retried in the same reset; check that chat before retrying manually. Individual
results appear in logs and in the selector's scrollable message area.

## Validation

Regression tests cover duplicate titles and profiles, pagination, read-only
metadata fallback, fragmented IPC frames, Unicode, pinned owner routing, partial
fan-out failure, stale windows, focus changes, malformed turn acknowledgments,
overlapping quota windows, stale snapshots, quota recovery, and reset retry
behavior. Native goal tests cover profile identity, preservation of budgets and
accounting, changed goals, startup recovery, retries, and uncertain activation.
An opt-in offline integration test uses two real installed Codex backends sharing
a temporary profile: native activation is visible to the original backend while
the control backend remains unloaded. Its model provider points only to a closed
local port; existing chats and external model services are never used. Live checks
exercise discovery and GTK selection/search/save using isolated configuration.
No test signal is sent to existing user chats.
