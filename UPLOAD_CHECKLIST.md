# Upload checklist

<p align="center">
  <img src="docs/assets/logo-lockup.png" width="200" alt="Recharge AI-task logo">
</p>

Repository: [Recharge AI-task](https://github.com/mikkovedru/recharge-ai-task)

## Source files

Commit project source, English documentation, tests, build scripts and workflows.
Include the resized artwork in `recharge_ai_task/assets/` and `docs/assets/`.
The English message catalog is `recharge_ai_task/locales/en.json`.
See [OPEN_SOURCE.md](OPEN_SOURCE.md) for the source layout and
[docs/branding.md](docs/branding.md) for artwork sizes.

## Keep local files out of Git

| Path | Purpose |
|------|---------|
| `dist/` | Built executables and packages; upload release archives as attachments |
| `build/` | PyInstaller intermediate files |
| `*.egg-info/` | Local Python package metadata |
| `.pytest_cache/`, `.venv/` | Test cache and development environment |
| Generated root-level `*.spec` files | Temporary PyInstaller build specifications |
| Original input artwork | Use converted project assets instead |
| `~/.recharge-ai-task/` | Private user settings |

Keep `AGENTS.md` local as instructed by the repository owner.
Review `git status` and the staged diff before committing to avoid including
private settings or unrelated local files.

## Git remotes and publishing

`origin` is the Recharge AI-task repository. `upstream` is the original
Autumnpoem repository. Development uses `master`.
For a checkout that already has both remotes:

```bash
git remote set-url origin https://github.com/mikkovedru/recharge-ai-task.git
git remote set-url upstream https://github.com/Autumnpoem/codex-autocontinue.git
git config remote.pushDefault origin
```

Push only when you intend to publish the reviewed commits:

```bash
git push -u origin master
```

## Release attachments

- `recharge-ai-task-windows-x86_64.zip`: CLI and combined desktop executables, plus the old GUI/tray command scripts.
- `recharge-ai-task-linux-x86_64.tar.gz`: CLI and combined desktop executables, plus the old GUI/tray shell launchers.

The desktop executable is `recharge-ai-task` and the CLI executable is
`recharge-ai-task-cli` (with `.exe` on Windows). Keep them together for
CLI/desktop integration. Build and tag releases using
[RELEASE.md](RELEASE.md). Python wheels and source distributions include the
English message catalog and converted program artwork.
