# 上传文件清单 / Upload checklist

仓库：[Recharge AI-task source](https://github.com/mikkovedru/codex-charge)

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

recharge_ai_task/__init__.py
recharge_ai_task/__main__.py
recharge_ai_task/autostart.py
recharge_ai_task/cli.py
recharge_ai_task/config.py
recharge_ai_task/configure.py
recharge_ai_task/desktop_input.py
recharge_ai_task/i18n.py
recharge_ai_task/parser.py
recharge_ai_task/pty_backend.py
recharge_ai_task/pty_unix.py
recharge_ai_task/pty_win.py
recharge_ai_task/quota.py
recharge_ai_task/tray.py
recharge_ai_task/watch.py
recharge_ai_task/wrapper.py
recharge_ai_task/locales/en.json
recharge_ai_task/locales/zh.json

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
| `recharge-ai-task-tray.spec` | PyInstaller 临时 spec（已 gitignore） |
| `scripts/debug_*.py` | 本地调试脚本（可选提交，默认不上传） |
| `~/.recharge-ai-task/` | 用户本地配置 |

## 首次推送命令

在项目根目录 `D:\recharge-ai-task` 执行：

```powershell
git remote add origin https://github.com/mikkovedru/codex-charge.git
git add .github .gitignore LICENSE MANIFEST.in pyproject.toml requirements.txt
git add README.md README_zh.md CONTRIBUTING.md RELEASE.md OPEN_SOURCE.md UPLOAD_CHECKLIST.md
git add docs/RELEASE_NOTES_v1.1.0.md
git add recharge_ai_task scripts/build_windows.ps1 scripts/build_linux.sh scripts/fake_codex.py
git add tests
git commit -m "Initial release: recharge-ai-task v1.1.0 — auto-continue Codex after quota resets"
git branch -M main
git push -u origin main
```

## Release 附件（不要进 git）

打 tag `v1.1.0` 后，在 Release 页上传：

- `recharge-ai-task-windows-x86_64.zip`（含 `recharge-ai-task.exe` + `recharge-ai-task-tray.exe`）
- `recharge-ai-task-linux-x86_64.tar.gz`（含 `recharge-ai-task` + `recharge-ai-task-tray`）

构建方法见 [RELEASE.md](RELEASE.md)。
