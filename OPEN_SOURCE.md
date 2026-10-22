# Open-source release layout

<p align="center">
  <img src="docs/assets/logo-lockup.png" width="200" alt="Recharge AI-task logo">
</p>

This document describes what ships in the public **MIT** repository and release artifacts.

## Repository (source)

```
recharge-ai-task/
├── LICENSE                 # MIT
├── README.md               # English documentation
├── RELEASE.md              # x86_64 release checklist
├── CONTRIBUTING.md
├── MANIFEST.in
├── pyproject.toml          # pip package metadata
├── recharge_ai_task/           # Main library
│   ├── cli.py              # CLI entry
│   ├── configure.py        # First-run: mode and defaults
│   ├── wrapper.py          # CLI mode (PTY)
│   ├── watch.py            # Desktop app mode
│   ├── desktop_input.py    # Window focus + keystrokes
│   ├── quota.py            # codex app-server quota API
│   ├── parser.py           # Terminal limit message parser
│   ├── i18n.py + locales/  # English messages
│   ├── tray.py             # System tray (Win + Linux)
│   ├── pty_win.py          # Windows PTY (pywinpty)
│   ├── pty_unix.py         # Linux PTY
│   └── config.py           # ~/.recharge-ai-task/config.json
├── scripts/
│   ├── build_windows.ps1   # x86_64 Windows exe
│   ├── build_linux.sh      # x86_64 Linux binaries
│   └── fake_codex.py       # E2E test helper
├── tests/
└── .github/workflows/ci.yml
```

**Not committed** (see `.gitignore`): `dist/`, `build/`, `*.egg-info/`, `.pytest_cache/`.

## What users install

| Channel | Audience | Command |
|---------|----------|---------|
| **PyPI** | Developers | `pip install "recharge-ai-task[all]"` then `recharge-ai-task-cli configure` |
| **GitHub Release** | End users without Python | Download platform zip, run `recharge-ai-task` |
| **From source** | Contributors | `pip install -e ".[all,dev]"` |

## Release binaries (x86_64 only)

| Platform | Files |
|----------|-------|
| Windows | `recharge-ai-task-cli.exe`, `recharge-ai-task.exe` |
| Ubuntu | `recharge-ai-task-cli`, `recharge-ai-task` |

The desktop binary contains both the dashboard and tray. Use `--tray` to start
without the dashboard. It can run independently; keep the CLI beside it to
support CLI actions from the tray and desktop launch commands from the CLI.
Linux also includes small `recharge-ai-task-gui` and `recharge-ai-task-tray`
compatibility scripts; Windows includes the matching `.cmd` files.
The GUI command is `recharge-ai-task`; the CLI command is `recharge-ai-task-cli`.

## Modes

| Mode | Target | How |
|------|--------|-----|
| `cli` | Codex CLI in terminal | PTY wrapper — most reliable |
| `desktop` | ChatGPT Codex desktop app | Poll quota API → type into window |

Desktop mode uses the same ChatGPT account / `codex app-server` auth as CLI. It does **not** hook into the Electron app internals.

## Before publishing

1. Repo URL is set to `https://github.com/mikkovedru/recharge-ai-task`.
2. Run `pytest tests/ -v` on Windows and Ubuntu.
3. Build x86_64 artifacts per `RELEASE.md`.
4. Tag e.g. `v1.1.0` and attach platform zips.
