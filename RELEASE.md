# Release checklist (x86_64)

Target: **Windows x86_64** + **Ubuntu x86_64** only.

Repository: https://github.com/Autumnpoem/codex-autocontinue

---

## 0. Pre-release

```bash
# Clone & install dev deps
git clone https://github.com/Autumnpoem/codex-autocontinue.git
cd codex-autocontinue

pip install -e ".[all,dev]"
pytest tests/ -v
```

Update version in `pyproject.toml` and `codex_charge/__init__.py` if bumping.

---

## 1. Build Windows (on Windows x86_64)

```powershell
cd D:\codex-charge
pip install "codex-charge[all,dev]"
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\package_release.ps1
```

**Output:**

| File | Purpose |
|------|---------|
| `dist\codex-charge.exe` | CLI wrapper |
| `dist\codex-charge-tray.exe` | Tray app (no console) |
| `dist\codex-charge-windows-x86_64.zip` | **Upload to GitHub Release** |

> Both `.exe` must stay in the **same folder** for the tray to work.

---

## 2. Build Ubuntu (on Ubuntu x86_64)

```bash
cd ~/codex-autocontinue
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
pip install "codex-charge[tray,dev]"
bash scripts/build_linux.sh
bash scripts/package_release.sh
chmod +x dist/codex-charge dist/codex-charge-tray
```

**Output:**

| File | Purpose |
|------|---------|
| `dist/codex-charge` | CLI wrapper |
| `dist/codex-charge-tray` | Tray app |
| `dist/codex-charge-linux-x86_64.tar.gz` | **Upload to GitHub Release** |

Linux desktop mode users also need: `sudo apt install xdotool` (X11).

> **Cannot cross-compile:** Linux binaries must be built on Linux. Use a Ubuntu VM, WSL2, or GitHub Actions if you only have Windows.

---

## 3. Test before release

**Windows:**

```powershell
cd dist
.\codex-charge.exe quota
.\codex-charge-tray.exe
# Tray → Show Quota / Start Codex (Goal)
```

**Ubuntu:**

```bash
cd dist
./codex-charge quota
./codex-charge-tray
```

Requires Codex CLI installed and logged in on the test machine.

---

## 4. Git tag & push

```bash
git tag v1.1.0
git push origin main
git push origin v1.1.0
```

---

## 5. Create GitHub Release

### Option A — Web UI

1. Open https://github.com/Autumnpoem/codex-autocontinue/releases/new
2. **Choose a tag:** `v1.1.0`
3. **Release title:** `v1.1.0`
4. **Description:** copy from [docs/RELEASE_NOTES_v1.1.0.md](docs/RELEASE_NOTES_v1.1.0.md)
5. **Attach files:**
   - `dist/codex-charge-windows-x86_64.zip`
   - `dist/codex-charge-linux-x86_64.tar.gz`
6. Click **Publish release**

### Option B — GitHub CLI (`gh`)

```bash
gh release create v1.1.0 \
  dist/codex-charge-windows-x86_64.zip \
  dist/codex-charge-linux-x86_64.tar.gz \
  --title "v1.1.0" \
  --notes-file docs/RELEASE_NOTES_v1.1.0.md
```

---

## 6. End-user install (from Release zip)

**Windows:**

1. Download `codex-charge-windows-x86_64.zip`
2. Extract to e.g. `C:\Tools\codex-charge\`
3. Double-click `codex-charge-tray.exe`
4. Right-click tray icon → Start Codex (Goal)
5. Prerequisite: [Codex CLI](https://github.com/openai/codex) installed & signed in

**Ubuntu:**

```bash
tar -xzf codex-charge-linux-x86_64.tar.gz -C ~/codex-charge
chmod +x ~/codex-charge/codex-charge ~/codex-charge/codex-charge-tray
~/codex-charge/codex-charge-tray
```

---

## PyPI (optional, separate from GitHub Release)

```bash
pip install build twine
python -m build
twine upload dist/codex-charge-*.tar.gz dist/codex_charge-*.whl
```

Users then: `pip install "codex-charge[all]"` + `codex-charge configure`
