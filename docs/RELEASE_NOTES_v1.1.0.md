# Release Notes — v1.1.0

<p align="center">
  <img src="assets/logo-lockup.png" width="200" alt="Recharge AI-task logo">
</p>

**Repository:** https://github.com/mikkovedru/recharge-ai-task

**Tag:** `v1.1.0`  
**License:** MIT

These notes describe a historical release. Current builds use English only;
see the [README](../README.md) for current setup. Current desktop builds combine
the dashboard and tray in `recharge-ai-task`; `--tray` starts without opening
the dashboard. The old tray command is a compatibility script.

---

## Release details

### 🎉 First public release

**Recharge AI-task** automatically resumes Codex after 5-hour / 7-day usage limits reset — no more babysitting long tasks.

### What's included

- **CLI mode** — PTY wrapper around `codex`; parses limit messages + official quota API fallback
- **Desktop mode** — watches quota API and types into the **ChatGPT Codex desktop app**
- **Language support** — the historical release offered a language selector; current builds use English only
- **System tray** — start/stop, quota view, autostart (Windows + Ubuntu)
- **Cross-platform** — Windows & Ubuntu **x86_64**

### Quick start

```bash
pip install "recharge-ai-task[all]"   # Windows
pip install "recharge-ai-task[tray]"  # Linux
recharge-ai-task-cli configure
recharge-ai-task-cli --goal               # CLI
recharge-ai-task-cli watch                # Desktop app
recharge-ai-task --tray               # Tray
```

### Downloads (x86_64)

| Platform | File |
|----------|------|
| Windows | `recharge-ai-task-windows-x86_64.zip` |
| Ubuntu | `recharge-ai-task-linux-x86_64.tar.gz` |

Each archive contains **two binaries** — place them in the same folder, then run `recharge-ai-task`.

### Requirements

- [Codex CLI](https://github.com/openai/codex) installed and signed in (ChatGPT account)
- Linux desktop mode: `sudo apt install xdotool` (X11 only)

### Full documentation

- [README — English](https://github.com/mikkovedru/recharge-ai-task#english)

---

## Checksums (fill after build)

```
# Windows zip
SHA256(recharge-ai-task-windows-x86_64.zip)=

# Linux tar.gz
SHA256(recharge-ai-task-linux-x86_64.tar.gz)=
```
