# Release Notes — v1.1.0

**Repository:** https://github.com/mikkovedru/codex-charge

**Tag:** `v1.1.0`  
**License:** MIT

---

## English

### 🎉 First public release

**Recharge AI-task** automatically resumes Codex after 5-hour / 7-day usage limits reset — no more babysitting long tasks.

### What's included

- **CLI mode** — PTY wrapper around `codex`; parses limit messages + official quota API fallback
- **Desktop mode** — watches quota API and types into the **ChatGPT Codex desktop app**
- **Bilingual UI** — English / 中文 (`recharge-ai-task configure`)
- **System tray** — start/stop, quota view, autostart (Windows + Ubuntu)
- **Cross-platform** — Windows & Ubuntu **x86_64**

### Quick start

```bash
pip install "recharge-ai-task[all]"   # Windows
pip install "recharge-ai-task[tray]"  # Linux
recharge-ai-task configure
recharge-ai-task --goal               # CLI
recharge-ai-task watch                # Desktop app
recharge-ai-task-tray                 # Tray
```

### Downloads (x86_64)

| Platform | File |
|----------|------|
| Windows | `recharge-ai-task-windows-x86_64.zip` |
| Ubuntu | `recharge-ai-task-linux-x86_64.tar.gz` |

Each archive contains **two binaries** — place them in the same folder, then run `recharge-ai-task-tray`.

### Requirements

- [Codex CLI](https://github.com/openai/codex) installed and signed in (ChatGPT account)
- Linux desktop mode: `sudo apt install xdotool` (X11 only)

### Full documentation

- [README — English](https://github.com/mikkovedru/codex-charge#english)
- [README — 中文](https://github.com/mikkovedru/codex-charge#中文)

---

## 中文

### 🎉 首次公开发布

**Recharge AI-task** 在 Codex 触达 5 小时 / 7 天限额后，自动等待额度恢复并发送 `继续` 或 `/goal resume`，长任务无需人工守着。

### 本版本包含

- **CLI 模式** — PTY 包装 `codex`；解析终端限额文案 + 官方 quota API 兜底
- **桌面版模式** — 监视额度 API，向 **ChatGPT Codex 桌面版** 自动输入
- **双语界面** — 英文 / 中文（`recharge-ai-task configure`）
- **系统托盘** — 启停、查看额度、开机自启（Windows + Ubuntu）
- **跨平台** — Windows 与 Ubuntu **x86_64**

### 快速开始

```bash
pip install "recharge-ai-task[all]"   # Windows
pip install "recharge-ai-task[tray]"  # Linux
recharge-ai-task configure
recharge-ai-task --goal               # CLI
recharge-ai-task watch                # 桌面版
recharge-ai-task-tray                 # 托盘
```

### 下载（x86_64）

| 平台 | 文件 |
|------|------|
| Windows | `recharge-ai-task-windows-x86_64.zip` |
| Ubuntu | `recharge-ai-task-linux-x86_64.tar.gz` |

每个压缩包含**两个可执行文件**，放在同一文件夹后运行 `recharge-ai-task-tray`。

### 环境要求

- 已安装并登录 [Codex CLI](https://github.com/openai/codex)（ChatGPT 账号）
- Linux 桌面模式：`sudo apt install xdotool`（仅 X11）

### 完整文档

- [README — English](https://github.com/mikkovedru/codex-charge#english)
- [README — 中文](https://github.com/mikkovedru/codex-charge#中文)

---

## Checksums (fill after build)

```
# Windows zip
SHA256(recharge-ai-task-windows-x86_64.zip)=

# Linux tar.gz
SHA256(recharge-ai-task-linux-x86_64.tar.gz)=
```
