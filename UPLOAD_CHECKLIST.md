# 上传文件清单 / Upload checklist

仓库：[Autumnpoem/codex-autocontinue](https://github.com/Autumnpoem/codex-autocontinue)

以下文件**需要**提交到 GitHub；其余目录已被 `.gitignore` 排除。

## ✅ 需要上传（共 38 项）

```
.github/workflows/ci.yml

.gitignore
LICENSE
MANIFEST.in
pyproject.toml
requirements.txt

README.md
README_zh.md
CONTRIBUTING.md
RELEASE.md
OPEN_SOURCE.md
UPLOAD_CHECKLIST.md
docs/RELEASE_NOTES_v1.1.0.md

codex_charge/__init__.py
codex_charge/__main__.py
codex_charge/autostart.py
codex_charge/cli.py
codex_charge/config.py
codex_charge/configure.py
codex_charge/desktop_input.py
codex_charge/i18n.py
codex_charge/parser.py
codex_charge/pty_backend.py
codex_charge/pty_unix.py
codex_charge/pty_win.py
codex_charge/quota.py
codex_charge/tray.py
codex_charge/watch.py
codex_charge/wrapper.py
codex_charge/locales/en.json
codex_charge/locales/zh.json

scripts/build_windows.ps1
scripts/build_linux.sh
scripts/fake_codex.py

tests/test_e2e_wrapper.py
tests/test_i18n.py
tests/test_parser.py
tests/test_smoke.py
tests/test_watch.py
```

## ❌ 不要上传

| 路径 | 原因 |
|------|------|
| `dist/` | 编译产物，放 GitHub **Release** 附件 |
| `build/` | PyInstaller 中间文件 |
| `*.egg-info/` | pip 本地安装缓存 |
| `.pytest_cache/` | 测试缓存 |
| `codex-charge-tray.spec` | PyInstaller 临时 spec（已 gitignore） |
| `scripts/debug_*.py` | 本地调试脚本（可选提交，默认不上传） |
| `~/.codex-charge/` | 用户本地配置 |

## 首次推送命令

在项目根目录 `D:\codex-charge` 执行：

```powershell
git remote add origin https://github.com/Autumnpoem/codex-autocontinue.git
git add .github .gitignore LICENSE MANIFEST.in pyproject.toml requirements.txt
git add README.md README_zh.md CONTRIBUTING.md RELEASE.md OPEN_SOURCE.md UPLOAD_CHECKLIST.md
git add docs/RELEASE_NOTES_v1.1.0.md
git add codex_charge scripts/build_windows.ps1 scripts/build_linux.sh scripts/fake_codex.py
git add tests
git commit -m "Initial release: codex-charge v1.1.0 — auto-continue Codex after quota resets"
git branch -M main
git push -u origin main
```

## Release 附件（不要进 git）

打 tag `v1.1.0` 后，在 Release 页上传：

- `codex-charge-windows-x86_64.zip`（含 `codex-charge.exe` + `codex-charge-tray.exe`）
- `codex-charge-linux-x86_64.tar.gz`（含 `codex-charge` + `codex-charge-tray`）

构建方法见 [RELEASE.md](RELEASE.md)。
