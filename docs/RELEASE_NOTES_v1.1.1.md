# Release Notes — v1.1.1

<p align="center">
  <img src="assets/logo-lockup.png" width="200" alt="Recharge AI-task logo">
</p>

**Repository:** https://github.com/mikkovedru/recharge-ai-task

**Tag:** `v1.1.1`  
**License:** MIT

---

## English

### Fixes in v1.1.1

- Fix PyInstaller bundles missing bilingual locale files (`en.json` / `zh.json`)
- Improve build scripts for reliable one-file executables on Windows & Ubuntu
- Add GitHub Actions workflow: push tag `v*` → auto-build Win + Linux → publish Release

### Downloads (x86_64)

| Platform | File |
|----------|------|
| Windows | `recharge-ai-task-windows-x86_64.zip` |
| Ubuntu | `recharge-ai-task-linux-x86_64.tar.gz` |

Each archive contains **two binaries** in one folder — run `recharge-ai-task-tray`.

### Quick start

1. Download the zip for your platform
2. Extract to a folder (both binaries must stay together)
3. Run `recharge-ai-task-tray` (or `recharge-ai-task-tray.exe` on Windows)
4. Prerequisite: [Codex CLI](https://github.com/openai/codex) installed & signed in

Full docs: [README](https://github.com/mikkovedru/recharge-ai-task#english)

---

## 中文

### v1.1.1 修复

- 修复 PyInstaller 打包后缺少双语语言包的问题
- 改进 Windows / Ubuntu 构建脚本
- 新增 GitHub Actions：推送 tag `v*` 后自动编译 Win + Linux 并发布 Release

### 下载（x86_64）

| 平台 | 文件 |
|------|------|
| Windows | `recharge-ai-task-windows-x86_64.zip` |
| Ubuntu | `recharge-ai-task-linux-x86_64.tar.gz` |

每个压缩包含**两个可执行文件**，放在同一文件夹后运行 `recharge-ai-task-tray`。

### 快速开始

1. 下载对应平台的压缩包
2. 解压（两个文件须同目录）
3. 运行 `recharge-ai-task-tray`（Windows 为 `.exe`）
4. 前提：已安装并登录 [Codex CLI](https://github.com/openai/codex)

完整文档：[README 中文](https://github.com/mikkovedru/recharge-ai-task#中文)
