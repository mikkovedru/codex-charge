# Contributing

<p align="center">
  <img src="docs/assets/logo-lockup.png" width="200" alt="Recharge AI-task logo">
</p>

Thank you for considering a contribution to Recharge AI-task.

## Development setup

```bash
git clone https://github.com/mikkovedru/recharge-ai-task.git recharge-ai-task
cd recharge-ai-task
git remote add upstream https://github.com/Autumnpoem/codex-autocontinue.git
git config remote.pushDefault origin
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[all,dev]"
pytest tests/ -v
```

`origin` is the Recharge AI-task repository. `upstream` is the original
Autumnpoem project, used to fetch upstream changes. Work on `master` and push
to `origin`.

## Platform notes

| OS | Extra deps |
|----|------------|
| Windows | `pip install "recharge-ai-task[windows]"` (pywinpty) |
| Linux tray | `pip install "recharge-ai-task[tray]"` |
| Linux desktop mode | `sudo apt install xdotool` (X11 only) |

## Pull requests

1. Keep changes focused; match existing style.
2. Add or update tests for behavior changes.
3. Run `pytest tests/ -v` before submitting.
4. Update `README.md` if user-facing behavior changes.

## Release targets

Official binaries are built for **x86_64** only:

- Windows: `scripts/build_windows.ps1`
- Ubuntu: `scripts/build_linux.sh`

See [RELEASE.md](RELEASE.md) for the full checklist.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
