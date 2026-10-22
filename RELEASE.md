# Release checklist (x86_64)

<p align="center">
  <img src="docs/assets/logo-lockup.png" width="200" alt="Recharge AI-task logo">
</p>

Target: **Windows x86_64** + **Ubuntu x86_64** only.

Repository: https://github.com/mikkovedru/recharge-ai-task

---

## 0. Pre-release

```bash
# Clone & install dev deps
git clone https://github.com/mikkovedru/recharge-ai-task.git recharge-ai-task
cd recharge-ai-task

pip install -e ".[all,dev]"
pytest tests/ -v
```

Update version in `pyproject.toml` and `recharge_ai_task/__init__.py` if bumping.

---

## 1. Build Windows (on Windows x86_64)

```powershell
cd D:\recharge-ai-task
pip install "recharge-ai-task[all,dev]"
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\package_release.ps1
```

**Output:**

| File | Purpose |
|------|---------|
| `dist\recharge-ai-task-cli.exe` | CLI wrapper |
| `dist\recharge-ai-task.exe` | Combined desktop app (tray on Windows, no console) |
| `dist\recharge-ai-task-windows-x86_64.zip` | **Upload to GitHub Release** |

> Keep both `.exe` in the same folder for CLI/tray integration. The desktop
> executable starts independently. A small `recharge-ai-task-tray.cmd` launcher
> preserves the previous tray command; `recharge-ai-task-gui.cmd` preserves
> the old GUI command.

---

## 2. Build Ubuntu (on Ubuntu x86_64)

```bash
cd ~/recharge-ai-task
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
pip install "recharge-ai-task[tray,dev]"
bash scripts/build_linux.sh
bash scripts/package_release.sh
chmod +x dist/recharge-ai-task-cli dist/recharge-ai-task
```

**Output:**

| File | Purpose |
|------|---------|
| `dist/recharge-ai-task-cli` | CLI wrapper |
| `dist/recharge-ai-task` | Combined dashboard and tray |
| `dist/recharge-ai-task-linux-x86_64.tar.gz` | **Upload to GitHub Release** |

Linux desktop mode users also need: `sudo apt install xdotool` (X11).

> **Cannot cross-compile:** Linux binaries must be built on Linux. Use a Ubuntu VM, WSL2, or GitHub Actions if you only have Windows.

---

## 3. Test before release

**Windows:**

```powershell
cd dist
.\recharge-ai-task-cli.exe quota
.\recharge-ai-task.exe
# Tray → Show Quota / Start Codex (Goal)
```

**Ubuntu:**

```bash
cd dist
./recharge-ai-task-cli quota
./recharge-ai-task          # Dashboard and tray
./recharge-ai-task-cli tray     # Start only the tray
./recharge-ai-task --tray   # Same, without requiring the CLI
```

The Linux archive contains two binaries (`recharge-ai-task` for the desktop
and `recharge-ai-task-cli` for terminal commands) plus small compatibility
launchers named `recharge-ai-task-gui` and `recharge-ai-task-tray`. Check that tray-only launch leaves the dashboard closed,
a GUI launch reuses the same tray, and closing the dashboard leaves its icon
running. The desktop binary must also launch when copied alone to another folder.
Codex actions require Codex CLI installed and logged in on the test machine.

---

## 4. Git tag & push

```bash
git tag v1.1.0
git push origin master
git push origin v1.1.0
```

---

## 5. Create GitHub Release

### Option A — Web UI

1. Open https://github.com/mikkovedru/recharge-ai-task/releases/new
2. **Choose a tag:** `v1.1.0`
3. **Release title:** `v1.1.0`
4. **Description:** copy from [docs/RELEASE_NOTES_v1.1.0.md](docs/RELEASE_NOTES_v1.1.0.md)
5. **Attach files:**
   - `dist/recharge-ai-task-windows-x86_64.zip`
   - `dist/recharge-ai-task-linux-x86_64.tar.gz`
6. Click **Publish release**

### Option B — GitHub CLI (`gh`)

```bash
gh release create v1.1.0 \
  dist/recharge-ai-task-windows-x86_64.zip \
  dist/recharge-ai-task-linux-x86_64.tar.gz \
  --title "v1.1.0" \
  --notes-file docs/RELEASE_NOTES_v1.1.0.md
```

---

## 6. End-user install (from Release zip)

**Windows:**

1. Download `recharge-ai-task-windows-x86_64.zip`
2. Extract to e.g. `C:\Tools\recharge-ai-task\`
3. Double-click `recharge-ai-task.exe`
4. Right-click tray icon → Start Codex (Goal)
5. Prerequisite: [Codex CLI](https://github.com/openai/codex) installed & signed in

**Ubuntu:**

```bash
tar -xzf recharge-ai-task-linux-x86_64.tar.gz -C ~/recharge-ai-task
chmod +x ~/recharge-ai-task/recharge-ai-task-cli ~/recharge-ai-task/recharge-ai-task
~/recharge-ai-task/recharge-ai-task
```

---

## PyPI (optional, separate from GitHub Release)

```bash
pip install build twine
python -m build
twine upload dist/recharge_ai_task-*.tar.gz dist/recharge_ai_task-*.whl
```

Users then: `pip install "recharge-ai-task[all]"` + `recharge-ai-task-cli configure`
