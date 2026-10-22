# Recharge AI-task

<p align="center">
  <img src="docs/assets/logo-lockup.png" width="360" alt="Recharge AI-task logo">
</p>

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Ubuntu%20x86__64-lightgrey.svg)](#release-builds-x86_64-only)

> Auto-continue Codex after 5h/7d quota resets — CLI PTY wrapper + ChatGPT Codex desktop watch, MIT.

The primary command, `recharge-ai-task`, opens the desktop app. Use
`recharge-ai-task-cli` for terminal operation.

### Usage at a glance

**CLI setup**

```bash
recharge-ai-task-cli configure          # choose mode (cli/desktop) and defaults
```

**For the Linux GUI, run `recharge-ai-task` and use Settings directly.**

**Then pick your workflow:**

| Scenario | What to run | Notes |
|-----------------|------------------------|--------------|
| **CLI + Goal mode** | `recharge-ai-task-cli --goal` | Wraps `codex` in terminal; first resume sends `/goal resume` |
| **CLI + normal** | `recharge-ai-task-cli` | Auto-sends `Continue` after reset |
| **CLI + task args** | `recharge-ai-task-cli --goal -- exec "your task"` | Pass args to codex after `--` |
| **Linux graphical dashboard** | `recharge-ai-task` | Select recipients, view quota, change settings, start/stop Desktop watch |
| **ChatGPT Codex desktop app** | `recharge-ai-task-cli watch` | Open Codex and save recipients in the GUI first |
| **Start directly in tray** | `recharge-ai-task --tray` or `recharge-ai-task-cli tray` | Starts without opening the dashboard or starting monitoring |
| **Check quota only** | `recharge-ai-task-cli quota` | Shows short/long window usage |
| **No Python (Release zip)** | Run `recharge-ai-task.exe` (Win) or `recharge-ai-task` (Linux) | Two binaries: CLI and combined desktop app. Keep them together for CLI integration; Codex CLI must be installed and signed in |

**Prerequisites:** Install [Codex CLI](https://github.com/openai/codex) and sign in with ChatGPT. Linux desktop mode also needs `sudo apt install xdotool` (X11). Native Goal signals use Codex's Resume goal control and require accessibility plus a clipboard manager (included in Mint Cinnamon). Source installs also need `python3-pyatspi`.

→ [Full guide](#english)

---

<a id="english"></a>

## Overview

Auto-continue **Codex CLI** and the **ChatGPT Codex desktop app** after 5-hour / 7-day usage limits reset.

When quota is exhausted, Recharge AI-task waits for recovery and the grace period, then continues selected tasks. Desktop recipients have independent Prompt and Goal signals; CLI Goal mode enters `/goal resume` in the terminal on its first recovery.

### Features

- **Two modes**
  - `cli` — PTY wrapper around `codex` in the terminal (most reliable)
  - `desktop` — watches quota and signals selected Codex chats or windows
- **Dual-channel reset detection (CLI mode)** — terminal message parsing + `codex app-server` quota API
- **Cross-platform** — Windows and Ubuntu (x86_64); `pip install` for developers
- **Optional tray app** — system tray on Windows & Linux (start/stop, quota, autostart)
- **MIT licensed** — open source, release-ready

### How it works

```
┌─────────────────────────────────────────────────────────────┐
│                       Recharge AI-task                      │
├──────────────────────────┬──────────────────────────────────┤
│      CLI mode (PTY)      │       Desktop mode (watch)        │
│  spawn codex in PTY      │  poll quota API every N seconds   │
│  parse terminal output   │  on 100% → sleep until reset      │
│  + quota API fallback    │  → type into desktop window       │
│  → write to PTY          │                                   │
└──────────────────────────┴──────────────────────────────────┘
                              │
                              ▼
                    codex app-server (quota API)
                    ChatGPT account / Codex CLI auth
```

**Why PTY for CLI?** Usage limits appear in the Codex CLI session. A PTY can read output and write input like a real terminal — no IDE plugin required.

**Why dual-channel parsing?** Terminal messages may change format; the official quota API is the fallback. We take the **later** reset time from both sources, then add a **60s grace** buffer to avoid edge-case jitter.

**Desktop delivery:** Desktop mode reads the quota API and addresses explicitly selected recipients. Linux chat targets use the running desktop’s private routing socket; window targets use keyboard input in the selected window. See [target discovery and delivery](docs/target-selection.md) for compatibility and focus requirements.

### Quick start

#### 1. Install

**Windows (full — CLI + tray):**

```powershell
pip install "recharge-ai-task[all]"
recharge-ai-task-cli configure
```

**Ubuntu / Debian (tray + desktop):**

```bash
sudo apt install xdotool    # required for desktop mode on X11
pip install "recharge-ai-task[tray]"
recharge-ai-task-cli configure
```

**CLI only (no tray):**

```bash
pip install recharge-ai-task
recharge-ai-task-cli configure --mode cli
```

#### 2. First-time setup (mode and defaults)

```bash
recharge-ai-task-cli configure
# non-interactive example:
recharge-ai-task-cli configure --mode desktop --goal
```

On first run in an interactive terminal, the setup wizard starts automatically if no config exists.

Config file: `~/.recharge-ai-task/config.json`

| Setting | Description |
|---------|-------------|
| `mode` | `cli` or `desktop` |
| `goal_mode` | CLI: first `/goal resume`; migration default for old Desktop selections |
| `grace_seconds` | Extra wait after reset (default `60`) |
| `continue_prompt` | Text to send (default `Continue`) |
| `desktop_targets` | Saved chat/window recipient identities |
| `poll_seconds` | Quota polling interval |
| `autostart` | Startup preference; the GUI also checks the OS registration |

#### 3. Run

```bash
# CLI mode (default when mode=cli)
recharge-ai-task-cli --goal
recharge-ai-task-cli --goal -- exec "your long task"

# Linux GUI: choose and save recipients, then start Desktop watch
recharge-ai-task
# Terminal watcher using the saved recipients
recharge-ai-task-cli watch

# Check quota
recharge-ai-task-cli quota

# Start only the system tray (Windows / Linux)
recharge-ai-task --tray
# Equivalent command through the CLI:
recharge-ai-task-cli tray
```

### Desktop app support

The **ChatGPT Codex desktop app** is supported via `desktop` mode:

1. Choose and save one or several chat/window recipients in the Linux GUI (or with `targets --select`).
2. Poll `codex app-server` quota API using the CLI account.
3. Wait for every exhausted window to recover, retain the grace period, and check fresh quota.
4. Signal each saved recipient once; retry confirmed failures independently.

Linux chat delivery uses exact IDs and the desktop router. X11 window delivery
requires `xdotool` and a focused composer. The GTK dashboard is available on
Linux. Windows uses CLI selection and window input. Legacy title-pattern
matching has been replaced by explicit recipients.

### Distribution options

| Method | Best for | How |
|--------|----------|-----|
| **Tray app** | Non-technical users | Download [GitHub Release](https://github.com/mikkovedru/recharge-ai-task/releases) zip, run `recharge-ai-task` |
| **Pre-built binary** | Users without Python | CLI plus one combined GUI/tray executable; no separate GUI runtime |
| **pip install** | Developers | `pip install "recharge-ai-task[all]"` |

> End users still need **Codex CLI installed and signed in** with a ChatGPT account. This tool only handles auto-continue after quota resets.

#### Tray menu

| Item | Action |
|------|--------|
| Start Codex (Goal) | New console, `--goal` mode |
| Start Codex (Normal) | Auto-send `Continue` after reset |
| Start Desktop Watch | Desktop app mode |
| Stop | End running process |
| Show Quota | Notification with usage |
| Settings… | Re-run configure wizard |
| Run at startup | Toggle autostart |
| Exit | Stop and quit tray |

The tray keeps the blue 5h recharge logo in both states. Its bottom strip is
**yellow** when idle and **green** when running; the tooltip also reports the state.

#### Autostart

| Platform | Mechanism |
|----------|-----------|
| Windows | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\recharge-ai-task-tray.bat` |
| Linux | `~/.config/autostart/recharge-ai-task-tray.desktop` |

Toggle via tray menu **Run at startup**.

### Release builds (x86_64 only)

Official binaries target **x86_64** on Windows and Ubuntu only (no ARM builds in official releases).

Build scripts keep generated PyInstaller specifications and intermediate files
under `build/`. Finished executables are written to `dist/`.

**Windows:**

```powershell
pip install "recharge-ai-task[all,dev]"
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
# → dist/recharge-ai-task-cli.exe, dist/recharge-ai-task.exe
```

**Ubuntu:**

```bash
pip install "recharge-ai-task[tray,dev]"
bash scripts/build_linux.sh
# → dist/recharge-ai-task-cli, dist/recharge-ai-task
```

The desktop executable runs independently for the GUI and tray. Keep the CLI
beside it to use CLI actions from the tray and to open the desktop from the CLI.
Linux includes small compatibility scripts named `recharge-ai-task-gui` and
`recharge-ai-task-tray`; Windows includes matching `.cmd` launchers. Neither
contains another bundled runtime.

**GitHub Release** (suggested attachments):

- `recharge-ai-task-windows-x86_64.zip`
- `recharge-ai-task-linux-x86_64.tar.gz`

**PyPI** (optional):

```bash
pip install build twine
python -m build
twine upload dist/recharge_ai_task-*.tar.gz dist/recharge_ai_task-*.whl
```

### Resource usage

| State | RAM | CPU |
|-------|-----|-----|
| Tray idle | ~30–50 MB | ~0% |
| CLI wrapper | +~5 MB over Codex | ~0% when waiting |
| Desktop watch | ~20–40 MB | ~0% (scheduled sleep) |
| Codex running | Codex itself dominates | task-dependent |
| Limit triggered | One quota API call (~1–2s) | brief spike |

You can leave the tray running in the background — it is lightweight. Codex itself is what consumes resources.

### CLI options

| Flag | Description | Default |
|------|-------------|---------|
| `--grace SECONDS` | Wait after reset | `60` |
| `--continue TEXT` | Auto-send text | `Continue` |
| `--goal` | First send `/goal resume` | off |
| `--codex PATH` | Codex executable | auto-detect |

The CLI, tray and dashboard use English. Language selectors and language
environment variables are no longer supported. Existing language preferences
are ignored, and the previous shipped continue prompt becomes `Continue`.
Custom prompts (including non-English text) and recipient choices are preserved.

### FAQ

**Does it support the new ChatGPT Codex desktop app?**  
Yes — use `desktop` mode or tray **Start Desktop Watch**. It uses the same quota API as CLI, not Electron hooks.

**Does it work with Cursor / VS Code?**  
It wraps **Codex CLI** in a terminal. IDE extensions are out of scope; run `recharge-ai-task-cli` in a terminal instead.

**What happens at quota reset?**  
Wait until `resets_at` from the official API (or parsed terminal message, whichever is later), plus 60 seconds grace, then send `Continue` or `/goal resume`.

**Can I run it 24/7?**  
Yes. Idle tray/watch uses negligible CPU; only Codex tasks consume meaningful resources.

### Project layout

```
recharge-ai-task/
├── recharge_ai_task/       # Main package
│   ├── cli.py          # Entry point
│   ├── configure.py    # Mode and defaults wizard
│   ├── wrapper.py      # CLI PTY mode
│   ├── watch.py        # Desktop watch mode
│   ├── tray.py         # System tray
│   ├── quota.py        # codex app-server API
│   ├── parser.py       # Limit message parser
│   ├── i18n.py         # Shared English messages
│   └── locales/        # English message catalog
├── scripts/            # build_*.ps1 / build_*.sh, fake_codex.py
├── tests/              # Automated regression tests
├── LICENSE             # MIT
├── RELEASE.md          # Release checklist
└── CONTRIBUTING.md
```

### Development

```bash
git clone https://github.com/mikkovedru/recharge-ai-task.git recharge-ai-task
cd recharge-ai-task
pip install -e ".[all,dev]"
pytest tests/ -v
```

Tests cover: English limit parsing, Goal mode E2E (fake Codex), desktop watch, real Codex spawn smoke.

See also: [CONTRIBUTING.md](CONTRIBUTING.md) · [RELEASE.md](RELEASE.md) · [OPEN_SOURCE.md](OPEN_SOURCE.md)

### Requirements

- Python 3.10+
- [Codex CLI](https://github.com/openai/codex) installed and signed in (ChatGPT account)
- Windows CLI mode: `pywinpty` (included in `[windows]` extra)
- Linux desktop mode: `xdotool` on X11

### Limitations

- Official release binaries: **x86_64 only** (Windows + Ubuntu)
- Desktop mode on Linux: **X11 only** (Wayland → use CLI mode)
- Requires local Codex CLI auth (`codex app-server` must work)
- Terminal limit message formats may change; quota API is the fallback

### Logs

When a limit is hit (CLI mode), stderr shows:

```text
[recharge-ai-task-cli] limit detected ('4 hours 12 minutes'), source=quota API, will send 'Continue' at 2026-07-13 04:01:00
[recharge-ai-task-cli] auto-continue sent
```

Log files: `~/.recharge-ai-task/tray.log`, `~/.recharge-ai-task/wrapper.log`

### GitHub repository

| Field | Value |
|-------|-------|
| **Repository** | [Recharge AI-task source](https://github.com/mikkovedru/recharge-ai-task) |
| **GUI / package name** | `recharge-ai-task` (also the pip install name) |
| **CLI command** | `recharge-ai-task-cli` |
| **Description** | Auto-continue Codex CLI & ChatGPT Codex desktop app after 5h/7d quota resets — Windows & Ubuntu x86_64, MIT |
| **License** | MIT |
| **Topics** | `codex`, `openai`, `chatgpt`, `automation`, `quota`, `rate-limit`, `cli`, `python`, `windows`, `linux`, `tray-app` |

Repository: [Recharge AI-task source](https://github.com/mikkovedru/recharge-ai-task)

### License

MIT — see [LICENSE](LICENSE).

---

## Project identity and upgrades

The application is **Recharge AI-task**. Its package and desktop command use
`recharge-ai-task`; terminal commands use `recharge-ai-task-cli`. The Python
package is `recharge_ai_task`.
Run `recharge-ai-task` for the dashboard.

Settings now live in `~/.recharge-ai-task/config.json`. On the first default
launch, existing settings from the previous name are copied byte for byte;
existing new settings are never overwritten and the original remains a backup.
Explicit `RECHARGE_AI_TASK_CONFIG_DIR` paths stay isolated. The previous
configuration-directory environment variable is accepted during upgrades,
with the new variable taking precedence. Language preferences are ignored.
Startup registration uses
`recharge-ai-task-tray.desktop` on Linux or `recharge-ai-task-tray.bat` on Windows;
enabling or disabling startup also retires its previous registration.

The GitHub repository is
[Recharge AI-task](https://github.com/mikkovedru/recharge-ai-task).
Use `origin` for this repository and `upstream` for
[Autumnpoem's original project](https://github.com/Autumnpoem/codex-autocontinue).
Development and releases use the `master` branch.

## Linux Mint Cinnamon

The tray uses the blue 5h recharge logo on an opaque white background with a dark border and a yellow (idle) or green (running) status strip. When Cinnamon's native XApp status applet is active, it uses XApp; with legacy or collapsible trays it uses an opaque XEmbed drawing surface at the actual allocated size, avoiding GTK StatusIcon caches and clipping. Image paths bypass symbolic icon recoloring; status is also shown by the tooltip and bottom color strip. Both left and right clicks open the menu. Cinnamon still controls the panel's icon size and whether its XApp status applet is visible.

```bash
sudo apt install python3-venv python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-3.0 gir1.2-xapp-1.0 python3-pyatspi gir1.2-atspi-2.0 xdotool
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e ".[tray,dev]"
PYTHON=.venv/bin/python bash scripts/build_linux.sh
./dist/recharge-ai-task --tray
```

Alternatively, run from source with `bash scripts/run_tray.sh`. The launcher works from any directory. Use `RECHARGE_AI_TASK_CONFIG_DIR` for isolated settings during checks; live quota tests require `RECHARGE_AI_TASK_LIVE_TESTS=1`. `PYSTRAY_BACKEND` can explicitly override the Cinnamon backend selection.


## Combined dashboard and tray

`recharge-ai-task` contains the dashboard and tray in one executable.
On Linux, normal launch opens the dashboard and starts its tray icon. To start
with only the icon, run either command:

```bash
recharge-ai-task --tray
recharge-ai-task-cli tray
```

Starting the tray does not start quota monitoring or send any signals.
If the app is already running, the tray command leaves the dashboard's current
visibility unchanged. `recharge-ai-task` opens or restores its dashboard.
Closing the dashboard keeps the tray and any active monitoring running.
The old `recharge-ai-task-gui` and `recharge-ai-task-tray` commands remain
compatibility launchers. CLI scripts must now use `recharge-ai-task-cli`;
`recharge-ai-task` opens the graphical app. `python -m recharge_ai_task` also
opens the graphical app; `python -m recharge_ai_task.cli` starts the CLI.
On Windows, the combined desktop executable starts in the tray by default;
the GTK dashboard remains Linux-only.

## Choose Codex signal recipients

The tray menu now has **Open Recharge AI-task…**. Select one or several chats or
windows; checkbox and prompt changes save automatically for quota-reset signals.
The picker shows titles,
thread/window IDs, process IDs, profiles, deep links, projects and live desktop
owners. Chat targets address a stable ID; window targets use the chat and focused
input currently shown in that window.

```bash
./dist/recharge-ai-task
./dist/recharge-ai-task-cli targets --gui
./dist/recharge-ai-task-cli targets --json
./dist/recharge-ai-task-cli targets --select THREAD_ID_1 --select THREAD_ID_2
```

After installing the Python package, use `recharge-ai-task`.
For a release archive, there are two binaries: CLI and combined desktop app.
`recharge-ai-task --help` lists desktop options including `--tray`;
`recharge-ai-task-cli --help` lists terminal commands. GUI launch commands also start the tray, or reuse the
running tray and bring its dashboard forward. Closing the window keeps the tray
and its watch available. Double-click the tray icon to hide the open dashboard
to the tray or restore it, preserving the current view. Right-click for the tray menu. Use **Exit** in that menu to quit the application.

The GUI saves checkbox and multiline prompt edits automatically, and shows
task and goal status refreshed every 15 seconds,
live quota usage and reset countdowns,
startup registration and launch origin, and the actual Desktop watch state.
Use **Start/Stop Desktop watch** and **Settings…** directly from this window.
Each row has independent **Send message** and **Resume goal** checkboxes.
Choices and message text save automatically for future quota recovery; editing
them does not send a manual signal. **Send now to N recipients** applies those
choices immediately, even with monitoring off. Its label shows the recipient
count, and the button is disabled when no recipients are selected:

- **Send message** sends only the configured message.
- **Resume goal** verifies native activation and continues the goal without a user prompt.
- **Both** verifies Goal activation first, then sends the prompt to continue work.
- **Neither** excludes the recipient. Window recipients support Send message only.

Goal activation preserves the existing objective, budget and usage history.
Manual sends may resume paused goals even while a prompt turn is running,
without adding a competing empty turn; automatic quota recovery respects intentional
pauses and skips blocked, completed, budget-limited or already-running goals.
An independently selected Prompt still sends when the Goal action is skipped;
a failed or unconfirmed Goal action prevents the subsequent prompt. Results for
each recipient appear in the window. Starting watch after quota has recovered
also recovers selected usage-limited goals, after the grace period.
The checkbox before **Run at login** enables or disables startup directly;
the watch button is above its **Desktop watch: On/Off** status, bordered green
when On, red when Off, and yellow while Stopping. **Refresh** sits directly
below the list; **Copy link / ID** and **Open selected row** are on its right.
The recipient summary and **Send now to N recipients** sit below the multiline message, with
the send button on the far right. **Project** shows the name assigned in Codex;
**Project path** retains the chat's working path. Both precede **Kind**.
Old selections migrate to Prompt, or Prompt + Goal when old goal recovery was enabled.
Saved changes automatically restart an active watch after a short debounce.
The previous worker finishes first, and quota-reset delivery accounting is
preserved. Empty selections or blank Prompt drafts suspend it until valid;
explicitly stopping the watch cancels pending restarts.

Choose targets before starting desktop watch. Local saved chats are included;
account-wide ChatGPT history and disconnected remote hosts are not enumerated.
See [the research, design and delivery notes](docs/target-selection.md) for protocol
compatibility, focus requirements and per-target retry behavior.
