# Release checklist (x86_64)

Target platforms: **Windows x86_64** and **Ubuntu x86_64** only.

## Pre-release

```bash
pip install -e ".[all,dev]"
pytest tests/ -v
```

Update version in `pyproject.toml` and `codex_charge/__init__.py`.

## Build

### Windows

```powershell
pip install "codex-charge[all,dev]"
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Artifacts:

- `dist/codex-charge.exe`
- `dist/codex-charge-tray.exe`

### Ubuntu (x86_64)

```bash
pip install "codex-charge[tray,dev]"
bash scripts/build_linux.sh
```

Artifacts:

- `dist/codex-charge`
- `dist/codex-charge-tray`

Linux desktop mode also requires: `sudo apt install xdotool` (X11).

## GitHub Release

1. Tag: `v1.1.0`
2. Attach four files (or two zips per platform):
   - `codex-charge-windows-x86_64.zip` — both `.exe`
   - `codex-charge-linux-x86_64.tar.gz` — both binaries
3. Release notes: copy from [docs/RELEASE_NOTES_v1.1.0.md](docs/RELEASE_NOTES_v1.1.0.md)

## PyPI (optional)

```bash
pip install build twine
python -m build
twine upload dist/codex-charge-*.tar.gz dist/codex_charge-*.whl
```

Users install with:

```bash
pip install "codex-charge[all]"   # Windows
pip install "codex-charge[tray]"  # Linux tray
codex-charge configure            # language + mode
```
