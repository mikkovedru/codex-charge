# Contributing

Thank you for considering a contribution to codex-charge.

## Development setup

```bash
git clone https://github.com/Autumnpoem/codex-autocontinue.git
cd codex-charge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[all,dev]"
pytest tests/ -v
```

## Platform notes

| OS | Extra deps |
|----|------------|
| Windows | `pip install "codex-charge[windows]"` (pywinpty) |
| Linux tray | `pip install "codex-charge[tray]"` |
| Linux desktop mode | `sudo apt install xdotool` (X11 only) |

## Pull requests

1. Keep changes focused; match existing style.
2. Add or update tests for behavior changes.
3. Run `pytest tests/ -v` before submitting.
4. Update `README.md` / `README_zh.md` if user-facing behavior changes.

## Release targets

Official binaries are built for **x86_64** only:

- Windows: `scripts/build_windows.ps1`
- Ubuntu: `scripts/build_linux.sh`

See [RELEASE.md](RELEASE.md) for the full checklist.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
