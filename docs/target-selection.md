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

Open **Choose signal targets…** in the tray, or run `codex-charge targets --gui`.
Search by title, ID, project, PID or deep link. Check several rows, edit the signal,
and use **Save selection** for quota-reset delivery. **Send signal now** sends the
visible text to the checked rows. **Open selected row** opens a chat without sending.
Metadata columns can be resized and scrolled; hovering a row shows full values.

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
Signals are text input; this path does not emulate the composer's slash-command
UI handlers. `/goal resume` is delivered as text to the selected chat.

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
that reset. Goal resume remains pending for a recipient until delivery succeeds. A timeout or
connection loss after submission is **uncertain**, so it is not automatically
retried in the same reset; check that chat before retrying manually. Individual
results appear in logs and in the selector's status tooltip.

## Validation

Regression tests cover duplicate titles and profiles, pagination, read-only
metadata fallback, fragmented IPC frames, Unicode, pinned owner routing, partial
fan-out failure, stale windows, focus changes, malformed turn acknowledgments,
overlapping quota windows, stale snapshots, quota recovery, and reset retry
behavior. Live checks
exercise discovery and GTK selection/search/save using isolated configuration.
No test signal is sent to existing user chats.
