# Release Notes — v1.1.1

<p align="center">
  <img src="assets/logo-lockup.png" width="200" alt="Recharge AI-task logo">
</p>

**Repository:** https://github.com/mikkovedru/recharge-ai-task

**Tag:** `v1.1.1`  
**License:** MIT

These notes describe a historical release. Current builds use English only;
see the [README](../README.md) for current setup. Current desktop builds combine
the dashboard and tray in `recharge-ai-task`; `--tray` starts without opening
the dashboard. The old tray command is a compatibility script.

---

## Release details

### Fixes in v1.1.1

- Fix PyInstaller bundles missing message catalogs; current builds include the English catalog
- Improve build scripts for reliable one-file executables on Windows & Ubuntu
- Add GitHub Actions workflow: push tag `v*` → auto-build Win + Linux → publish Release

### Downloads (x86_64)

| Platform | File |
|----------|------|
| Windows | `recharge-ai-task-windows-x86_64.zip` |
| Ubuntu | `recharge-ai-task-linux-x86_64.tar.gz` |

Each archive contains **two binaries** in one folder — run `recharge-ai-task`.

### Quick start

1. Download the zip for your platform
2. Extract to a folder (both binaries must stay together)
3. Run `recharge-ai-task` (or `recharge-ai-task.exe` on Windows)
4. Prerequisite: [Codex CLI](https://github.com/openai/codex) installed & signed in

Full docs: [README](https://github.com/mikkovedru/recharge-ai-task#english)

---
