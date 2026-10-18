# Recharge AI-task

<p align="center">
  <img src="docs/assets/logo-lockup.png" width="360" alt="Recharge AI-task logo">
</p>

<p align="center">
  <strong>Language / 语言</strong>：
  <a href="#english"><strong>English</strong></a> · <a href="#中文"><strong>中文</strong></a>
</p>

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Ubuntu%20x86__64-lightgrey.svg)](#release-builds-x86_64-only)

> **One-line summary / 一句话介绍**  
> EN: Auto-continue Codex after 5h/7d quota resets — CLI PTY wrapper + ChatGPT Codex desktop watch, bilingual, MIT.  
> 中文：Codex 5 小时/7 天限额恢复后自动继续 — 支持 CLI 与 ChatGPT Codex 桌面版，双语，MIT 开源。

### Usage at a glance / 用法速查

**CLI setup / CLI 首次设置**

```bash
recharge-ai-task configure          # pick language (en/zh) + mode (cli/desktop)
```

**For the Linux GUI, run `recharge-ai-task gui` and use Settings directly.**

**Then pick your workflow / 然后按场景选一种：**

| Scenario / 场景 | What to run / 运行命令 | Notes / 说明 |
|-----------------|------------------------|--------------|
| **CLI + Goal mode** | `recharge-ai-task --goal` | Wraps `codex` in terminal; first resume sends `/goal resume` |
| **CLI + normal** | `recharge-ai-task` | Auto-sends `继续` after reset |
| **CLI + task args** | `recharge-ai-task --goal -- exec "your task"` | Pass args to codex after `--` |
| **Linux graphical dashboard** | `recharge-ai-task gui` or `recharge-ai-task-gui` | Select recipients, view quota, change settings, start/stop Desktop watch |
| **ChatGPT Codex desktop app** | `recharge-ai-task watch` | Open Codex and save recipients in the GUI first |
| **System tray (easiest)** | `recharge-ai-task-tray` | Right-click tray icon → Start / Stop / Quota |
| **Check quota only** | `recharge-ai-task quota` | Shows short/long window usage |
| **No Python (Release zip)** | Run `recharge-ai-task-tray.exe` (Win) or `recharge-ai-task-tray` (Linux) | Keep release binaries in the **same folder** (three on Linux, two on Windows); still need Codex CLI installed & logged in |

**Pre-requisites / 前置条件：** Install [Codex CLI](https://github.com/openai/codex) and sign in with ChatGPT. Linux desktop mode also needs `sudo apt install xdotool` (X11). Native Goal signals use Codex's Resume goal control and require accessibility plus a clipboard manager (included in Mint Cinnamon). Source installs also need `python3-pyatspi`.

→ Full guide: [English](#english) · [中文](#中文)

---

<a id="english"></a>

## English

Auto-continue **Codex CLI** and the **ChatGPT Codex desktop app** after 5-hour / 7-day usage limits reset.

When quota is exhausted, Recharge AI-task waits for recovery and the grace period, then continues selected tasks. Desktop recipients have independent Prompt and Goal signals; CLI Goal mode enters `/goal resume` in the terminal on its first recovery.

### Features

- **Two modes**
  - `cli` — PTY wrapper around `codex` in the terminal (most reliable)
  - `desktop` — watches quota and signals selected Codex chats or windows
- **Dual-channel reset detection (CLI mode)** — terminal message parsing + `codex app-server` quota API
- **Bilingual CLI and tray** — English / 中文; the Linux GTK dashboard currently uses English
- **Cross-platform** — Windows and Ubuntu (x86_64); `pip install` for developers
- **Optional tray app** — system tray on Windows & Linux (start/stop, quota, autostart)
- **MIT licensed** — open source, release-ready

### How it works

```
┌─────────────────────────────────────────────────────────────┐
│                       Recharge AI-task                      │
├──────────────────────────┬──────────────────────────────────┤
│      CLI mode (PTY)      │       Desktop mode (watch)        │
│  spawn codex in PTY      │  poll quota API every N seconds   │
│  parse terminal output   │  on 100% → sleep until reset      │
│  + quota API fallback    │  → type into desktop window       │
│  → write to PTY          │                                   │
└──────────────────────────┴──────────────────────────────────┘
                              │
                              ▼
                    codex app-server (quota API)
                    ChatGPT account / Codex CLI auth
```

**Why PTY for CLI?** Usage limits appear in the Codex CLI session. A PTY can read output and write input like a real terminal — no IDE plugin required.

**Why dual-channel parsing?** Terminal messages may change format; the official quota API is the fallback. We take the **later** reset time from both sources, then add a **60s grace** buffer to avoid edge-case jitter.

**Desktop delivery:** Desktop mode reads the quota API and addresses explicitly selected recipients. Linux chat targets use the running desktop’s private routing socket; window targets use keyboard input in the selected window. See [target discovery and delivery](docs/target-selection.md) for compatibility and focus requirements.

### Quick start

#### 1. Install

**Windows (full — CLI + tray):**

```powershell
pip install "recharge-ai-task[all]"
recharge-ai-task configure
```

**Ubuntu / Debian (tray + desktop):**

```bash
sudo apt install xdotool    # required for desktop mode on X11
pip install "recharge-ai-task[tray]"
recharge-ai-task configure
```

**CLI only (no tray):**

```bash
pip install recharge-ai-task
recharge-ai-task configure --lang en --mode cli
```

#### 2. First-time setup (language + mode)

```bash
recharge-ai-task configure
# non-interactive example:
recharge-ai-task configure --lang zh --mode desktop --goal
```

On first run in an interactive terminal, the setup wizard starts automatically if no config exists.

Config file: `~/.recharge-ai-task/config.json`

| Setting | Description |
|---------|-------------|
| `language` | `en` or `zh` |
| `mode` | `cli` or `desktop` |
| `goal_mode` | CLI: first `/goal resume`; migration default for old Desktop selections |
| `grace_seconds` | Extra wait after reset (default `60`) |
| `continue_prompt` | Text to send (default `继续`) |
| `desktop_targets` | Saved chat/window recipient identities |
| `poll_seconds` | Quota polling interval |
| `autostart` | Startup preference; the GUI also checks the OS registration |

#### 3. Run

```bash
# CLI mode (default when mode=cli)
recharge-ai-task --goal
recharge-ai-task --goal -- exec "your long task"

# Linux GUI: choose and save recipients, then start Desktop watch
recharge-ai-task gui
# Terminal watcher using the saved recipients
recharge-ai-task watch

# Check quota
recharge-ai-task quota

# System tray (Windows / Linux)
recharge-ai-task-tray
```

### Desktop app support

The **ChatGPT Codex desktop app** is supported via `desktop` mode:

1. Choose and save one or several chat/window recipients in the Linux GUI (or with `targets --select`).
2. Poll `codex app-server` quota API using the CLI account.
3. Wait for every exhausted window to recover, retain the grace period, and check fresh quota.
4. Signal each saved recipient once; retry confirmed failures independently.

Linux chat delivery uses exact IDs and the desktop router. X11 window delivery
requires `xdotool` and a focused composer. The GTK dashboard is available on
Linux. Windows uses CLI selection and window input. Legacy title-pattern
matching has been replaced by explicit recipients.

### Distribution options

| Method | Best for | How |
|--------|----------|-----|
| **Tray app** | Non-technical users | Download [GitHub Release](https://github.com/mikkovedru/recharge-ai-task/releases) zip, run `recharge-ai-task-tray` |
| **Pre-built binary** | Users without Python | Keep release executables together; Linux also includes `recharge-ai-task-gui` |
| **pip install** | Developers | `pip install "recharge-ai-task[all]"` |

> End users still need **Codex CLI installed and signed in** with a ChatGPT account. This tool only handles auto-continue after quota resets.

#### Tray menu

| Item | Action |
|------|--------|
| Start Codex (Goal) | New console, `--goal` mode |
| Start Codex (Normal) | Auto-send `继续` after reset |
| Start Desktop Watch | Desktop app mode |
| Stop | End running process |
| Show Quota | Notification with usage |
| Settings… | Re-run configure wizard |
| Run at startup | Toggle autostart |
| Exit | Stop and quit tray |

The tray keeps the blue 5h recharge logo in both states. Its bottom strip is
**yellow** when idle and **green** when running; the tooltip also reports the state.

#### Autostart

| Platform | Mechanism |
|----------|-----------|
| Windows | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\recharge-ai-task-tray.bat` |
| Linux | `~/.config/autostart/recharge-ai-task-tray.desktop` |

Toggle via tray menu **Run at startup**.

### Release builds (x86_64 only)

Official binaries target **x86_64** on Windows and Ubuntu only (no ARM builds in official releases).

**Windows:**

```powershell
pip install "recharge-ai-task[all,dev]"
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
# → dist/recharge-ai-task.exe, dist/recharge-ai-task-tray.exe
```

**Ubuntu:**

```bash
pip install "recharge-ai-task[tray,dev]"
bash scripts/build_linux.sh
# → dist/recharge-ai-task, dist/recharge-ai-task-tray
```

Copy **both** binaries into the same folder before using the tray.

**GitHub Release** (suggested attachments):

- `recharge-ai-task-windows-x86_64.zip`
- `recharge-ai-task-linux-x86_64.tar.gz`

**PyPI** (optional):

```bash
pip install build twine
python -m build
twine upload dist/recharge_ai_task-*.tar.gz dist/recharge_ai_task-*.whl
```

### Resource usage

| State | RAM | CPU |
|-------|-----|-----|
| Tray idle | ~30–50 MB | ~0% |
| CLI wrapper | +~5 MB over Codex | ~0% when waiting |
| Desktop watch | ~20–40 MB | ~0% (scheduled sleep) |
| Codex running | Codex itself dominates | task-dependent |
| Limit triggered | One quota API call (~1–2s) | brief spike |

You can leave the tray running in the background — it is lightweight. Codex itself is what consumes resources.

### CLI options

| Flag | Description | Default |
|------|-------------|---------|
| `--grace SECONDS` | Wait after reset | `60` |
| `--continue TEXT` | Auto-send text | `继续` |
| `--goal` | First send `/goal resume` | off |
| `--codex PATH` | Codex executable | auto-detect |

Environment: `RECHARGE_AI_TASK_LANG=zh` · Config: `"language": "zh"`

### FAQ

**Does it support the new ChatGPT Codex desktop app?**  
Yes — use `desktop` mode or tray **Start Desktop Watch**. It uses the same quota API as CLI, not Electron hooks.

**Does it work with Cursor / VS Code?**  
It wraps **Codex CLI** in a terminal. IDE extensions are out of scope; run `recharge-ai-task` in a terminal instead.

**What happens at quota reset?**  
Wait until `resets_at` from the official API (or parsed terminal message, whichever is later), plus 60 seconds grace, then send `继续` or `/goal resume`.

**Can I run it 24/7?**  
Yes. Idle tray/watch uses negligible CPU; only Codex tasks consume meaningful resources.

### Project layout

```
recharge-ai-task/
├── recharge_ai_task/       # Main package
│   ├── cli.py          # Entry point
│   ├── configure.py    # Language + mode wizard
│   ├── wrapper.py      # CLI PTY mode
│   ├── watch.py        # Desktop watch mode
│   ├── tray.py         # System tray
│   ├── quota.py        # codex app-server API
│   ├── parser.py       # Limit message parser
│   ├── i18n.py         # en / zh
│   └── locales/        # Translation files
├── scripts/            # build_*.ps1 / build_*.sh, fake_codex.py
├── tests/              # pytest (11 tests)
├── LICENSE             # MIT
├── RELEASE.md          # Release checklist
└── CONTRIBUTING.md
```

### Development

```bash
git clone https://github.com/mikkovedru/recharge-ai-task.git recharge-ai-task
cd recharge-ai-task
pip install -e ".[all,dev]"
pytest tests/ -v
```

Tests cover: limit parsing (EN/ZH), Goal mode E2E (fake Codex), desktop watch, real Codex spawn smoke.

See also: [CONTRIBUTING.md](CONTRIBUTING.md) · [RELEASE.md](RELEASE.md) · [OPEN_SOURCE.md](OPEN_SOURCE.md)

### Requirements

- Python 3.10+
- [Codex CLI](https://github.com/openai/codex) installed and signed in (ChatGPT account)
- Windows CLI mode: `pywinpty` (included in `[windows]` extra)
- Linux desktop mode: `xdotool` on X11

### Limitations

- Official release binaries: **x86_64 only** (Windows + Ubuntu)
- Desktop mode on Linux: **X11 only** (Wayland → use CLI mode)
- Requires local Codex CLI auth (`codex app-server` must work)
- Terminal limit message formats may change; quota API is the fallback

### Logs

When a limit is hit (CLI mode), stderr shows:

```text
[recharge-ai-task] limit detected ('4 hours 12 minutes'), source=quota API, will send '继续' at 2026-07-13 04:01:00
[recharge-ai-task] auto-continue sent
```

Log files: `~/.recharge-ai-task/tray.log`, `~/.recharge-ai-task/wrapper.log`

### GitHub repository

| Field | Value |
|-------|-------|
| **Repository** | [Recharge AI-task source](https://github.com/mikkovedru/recharge-ai-task) |
| **CLI / package name** | `recharge-ai-task` (pip install name) |
| **Description** | Auto-continue Codex CLI & ChatGPT Codex desktop app after 5h/7d quota resets — bilingual, Windows & Ubuntu x86_64, MIT |
| **License** | MIT |
| **Topics** | `codex`, `openai`, `chatgpt`, `automation`, `quota`, `rate-limit`, `cli`, `python`, `windows`, `linux`, `tray-app` |

Repository: [Recharge AI-task source](https://github.com/mikkovedru/recharge-ai-task)

### License

MIT — see [LICENSE](LICENSE).

---

<a id="中文"></a>

## 中文

在 **Codex CLI** 或 **ChatGPT Codex 桌面版** 触达 5 小时 / 7 天限额后，自动等待额度恢复。桌面目标恢复通过原生 API 激活额度受限目标并发送继续文本；CLI 目标模式首次在终端提交 `/goal resume`。

### 特性

- **双目标**
  - `cli` — 终端 PTY 包装 Codex（最稳定）
  - `desktop` — 监视额度 API，向 ChatGPT Codex 桌面窗口自动输入
- **双通道检测（CLI 模式）** — 终端限额文案解析 + `codex app-server` 官方额度 API
- **双语界面** — 安装时选择 `en` / `zh`
- **跨平台** — Windows + Ubuntu（x86_64）；开发者可用 `pip install`
- **托盘应用** — 右下角启停、查看额度、开机自启（Win + Linux）
- **MIT 开源** — 可直接发布

### 原理

```
┌─────────────────────────────────────────────────────────────┐
│                       Recharge AI-task                      │
├──────────────────────────┬──────────────────────────────────┤
│      CLI 模式（PTY）      │      桌面版模式（watch）          │
│  伪终端启动 codex         │  轮询 quota API                   │
│  解析终端限额文案         │  100% → 等到重置时间              │
│  + quota API 兜底         │  → 聚焦窗口并自动输入             │
│  → 向 PTY 写入继续指令    │                                   │
└──────────────────────────┴──────────────────────────────────┘
                              │
                              ▼
                    codex app-server（额度 API）
                    ChatGPT 账号 / Codex CLI 登录态
```

**为什么 CLI 用 PTY？** 限额发生在 Codex 终端会话里，PTY 能同时读输出、写输入，不依赖 Cursor 或其他 IDE 插件。

**为什么双通道？** 终端文案可能随版本变化；官方 quota API 作兜底。两个来源取**更晚**的重置时间，再加 **60 秒** grace，避免卡在边界。

**桌面版怎么做？** ChatGPT Codex 已并入 ChatGPT 桌面应用，无法 PTY 包装。`desktop` 模式轮询同一套 `codex app-server` API，到点后向窗口发按键——**不** hook Electron 内部。

### 快速开始

#### 1. 安装

**Windows（完整版）：**

```powershell
pip install "recharge-ai-task[all]"
recharge-ai-task configure
```

**Ubuntu / Debian：**

```bash
sudo apt install xdotool    # 桌面模式需要（X11）
pip install "recharge-ai-task[tray]"
recharge-ai-task configure
```

**仅 CLI（无托盘）：**

```bash
pip install recharge-ai-task
recharge-ai-task configure --lang zh --mode cli
```

#### 2. 首次配置（语言 + 模式）

```bash
recharge-ai-task configure
# 非交互示例：
recharge-ai-task configure --lang zh --mode desktop --goal
```

在交互式终端首次运行且尚无配置文件时，会自动进入配置向导。

配置文件：`~/.recharge-ai-task/config.json`

| 配置项 | 说明 |
|--------|------|
| `language` | `en` 或 `zh` |
| `mode` | `cli` 或 `desktop` |
| `goal_mode` | CLI：首次发送 `/goal resume`；旧版桌面选择的迁移默认值 |
| `grace_seconds` | 恢复后额外等待秒数（默认 `60`） |
| `continue_prompt` | 自动发送文本（默认 `继续`） |
| `desktop_window_titles` | 桌面版窗口标题匹配 |

#### 3. 运行

```bash
# CLI 模式（mode=cli 时默认）
recharge-ai-task --goal
recharge-ai-task --goal -- exec "你的长任务"

# 桌面版（请先打开 ChatGPT Codex 桌面应用）
recharge-ai-task watch

# 查看额度
recharge-ai-task quota

# 系统托盘
recharge-ai-task-tray
```

### 桌面版 Codex 支持

**支持。** ChatGPT Codex 桌面版使用 `desktop` 模式：

1. 通过 `codex app-server` 读取官方额度（与 CLI 相同 ChatGPT 账号）
2. 检测到 100% 后，等到 `resets_at + 60秒`
3. 聚焦 Codex 窗口并自动输入继续指令

| 平台 | 输入方式 |
|------|----------|
| Windows | 内置（剪贴板粘贴 + Enter） |
| Ubuntu X11 | `xdotool`（`sudo apt install xdotool`） |
| Ubuntu Wayland | 暂不支持，请用 `cli` 模式 |

默认匹配窗口标题：`Codex`、`ChatGPT`、`OpenAI Codex`。可在配置中覆盖：

```json
{
  "desktop_window_titles": ["Codex", "自定义标题"]
}
```

### 给别人用：三种方式

| 方式 | 适合谁 | 操作 |
|------|--------|------|
| **托盘小应用** | 不想碰命令行 | 下载 [GitHub Release](https://github.com/mikkovedru/recharge-ai-task/releases) 压缩包，运行 `recharge-ai-task-tray` |
| **打包 exe** | 没有 Python 的用户 | 同一文件夹放两个可执行文件 |
| **pip 安装** | 开发者 | `pip install "recharge-ai-task[all]"` + `configure` |

对方电脑仍需已安装 **Codex CLI** 并登录 ChatGPT；本工具只负责限额恢复后的自动继续。

#### 托盘菜单

| 菜单项 | 作用 |
|--------|------|
| 启动 Codex（Goal） | 新开控制台，`--goal` 模式 |
| 启动 Codex（普通） | 恢复后自动发「继续」 |
| 启动桌面版监视 | 桌面应用模式 |
| 停止 | 结束当前进程 |
| 查看额度 | 气泡通知显示用量 |
| 设置… | 重新运行配置向导 |
| 开机自启 | 写入系统启动项 |
| 退出 | 停止并退出托盘 |

图标：**灰色** = 空闲，**绿色** = 运行中。

#### 开机自启

| 平台 | 机制 |
|------|------|
| Windows | `%APPDATA%\...\Startup\recharge-ai-task-tray.bat` |
| Linux | `~/.config/autostart/recharge-ai-task-tray.desktop` |

在托盘菜单勾选 **开机自启** 即可；取消勾选会删除启动项。

### 发布版（仅 x86_64）

官方 Release 仅提供 **Windows x86_64** 和 **Ubuntu x86_64**（不含 ARM）。

**Windows：**

```powershell
pip install "recharge-ai-task[all,dev]"
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
# → dist\recharge-ai-task.exe, dist\recharge-ai-task-tray.exe
```

**Ubuntu：**

```bash
pip install "recharge-ai-task[tray,dev]"
bash scripts/build_linux.sh
# → dist/recharge-ai-task, dist/recharge-ai-task-tray
```

**两个可执行文件必须放在同一目录** 才能使用托盘。

**GitHub Release** 建议附件：

- `recharge-ai-task-windows-x86_64.zip`
- `recharge-ai-task-linux-x86_64.tar.gz`

**PyPI**（可选）：

```bash
pip install "recharge-ai-task[all]"    # Windows
pip install "recharge-ai-task[tray]"   # Linux 托盘
recharge-ai-task configure             # 选语言 + 模式
```

### 资源占用

| 状态 | 内存 | CPU |
|------|------|-----|
| 仅托盘（空闲） | ~30–50 MB | ≈ 0% |
| CLI 包装运行中 | Codex 自身 + ~5 MB | 等待时 ≈ 0% |
| 桌面版监视 | ~20–40 MB | ≈ 0%（定时睡眠） |
| Codex 执行任务 | 主要是 Codex | 取决于任务 |
| 触发限额时 | 额外一次 API（~1–2 秒） | 短暂 |

托盘可以一直开着，几乎不占资源；真正吃资源的是 Codex 本身。

### 命令行选项

| 选项 | 说明 | 默认 |
|------|------|------|
| `--grace SECONDS` | 恢复后再等多长时间 | `60` |
| `--continue TEXT` | 自动发送的文本 | `继续` |
| `--goal` | 首次发 `/goal resume` | 关 |
| `--codex PATH` | 指定 codex 路径 | 自动查找 |

环境变量：`RECHARGE_AI_TASK_LANG=zh` · 配置：`"language": "zh"`

### 常见问题

**支持新的 ChatGPT Codex 桌面版吗？**  
支持。使用 `desktop` 模式或托盘「启动桌面版监视」，走与 CLI 相同的 quota API，不 hook Electron。

**能在 Cursor / VS Code 里用吗？**  
本工具包装的是 **Codex CLI 终端**。IDE 插件不在范围内；请在终端里运行 `recharge-ai-task`。

**额度恢复后会怎样？**  
等到官方 API 的 `resets_at`（或与终端解析结果中更晚的那个）+ 60 秒 grace，然后自动发送 `继续` 或 `/goal resume`。

**可以 24 小时挂着吗？**  
可以。空闲时 CPU 几乎为 0，主要资源消耗来自 Codex 任务本身。

### 项目结构

```
recharge-ai-task/
├── recharge_ai_task/       # 主程序包
│   ├── cli.py          # 命令行入口
│   ├── configure.py    # 语言 + 模式配置向导
│   ├── wrapper.py      # CLI PTY 模式
│   ├── watch.py        # 桌面版监视模式
│   ├── tray.py         # 系统托盘
│   ├── quota.py        # codex app-server API
│   ├── parser.py       # 限额文案解析
│   ├── i18n.py         # 国际化 en / zh
│   └── locales/        # 翻译文件
├── scripts/            # 构建脚本、测试用 fake_codex
├── tests/              # pytest（11 项测试）
├── LICENSE             # MIT
├── RELEASE.md          # 发布清单
└── CONTRIBUTING.md     # 贡献指南
```

### 开发与测试

```bash
git clone https://github.com/mikkovedru/recharge-ai-task.git recharge-ai-task
cd recharge-ai-task
pip install -e ".[all,dev]"
pytest tests/ -v
```

测试覆盖：中英限额文案解析、Goal 模式端到端（fake Codex）、桌面监视、真实 Codex 启动冒烟。

详见：[CONTRIBUTING.md](CONTRIBUTING.md) · [RELEASE.md](RELEASE.md) · [OPEN_SOURCE.md](OPEN_SOURCE.md)

### 环境要求

- Python 3.10+
- 已安装并登录 [Codex CLI](https://github.com/openai/codex)（ChatGPT 账号）
- Windows CLI 模式：需要 `pywinpty`（`[windows]` 依赖已包含）
- Linux 桌面模式：X11 下需 `xdotool`

### 限制说明

- 官方 Release 二进制：**仅 x86_64**（Windows + Ubuntu）
- Linux 桌面模式：**仅 X11**（Wayland 请用 CLI 模式）
- 需要本机 Codex CLI 已登录（`codex app-server` 可用）
- 终端限额文案格式可能变化；quota API 作兜底

### 日志示例

CLI 模式触限时的 stderr：

```text
[recharge-ai-task] limit detected ('4 hours 12 minutes'), source=quota API, will send '继续' at 2026-07-13 04:01:00
[recharge-ai-task] auto-continue sent
```

日志文件：`~/.recharge-ai-task/tray.log`、`~/.recharge-ai-task/wrapper.log`

### GitHub 仓库

| 字段 | 值 |
|------|-----|
| **Repository** | [Recharge AI-task source](https://github.com/mikkovedru/recharge-ai-task) |
| **CLI / 包名** | `recharge-ai-task`（pip 安装名） |
| **Description** | Auto-continue Codex CLI & ChatGPT Codex desktop app after 5h/7d quota resets — bilingual, Windows & Ubuntu x86_64, MIT |
| **Description（中文参考）** | Codex 5h/7d 限额恢复后自动继续（CLI + ChatGPT 桌面版）· 双语 · Win/Ubuntu x86_64 · MIT |
| **License** | MIT |
| **Topics** | `codex`, `openai`, `chatgpt`, `automation`, `quota`, `rate-limit`, `cli`, `python`, `windows`, `linux`, `tray-app` |

仓库地址：[Recharge AI-task source](https://github.com/mikkovedru/recharge-ai-task)

### 许可

MIT — 见 [LICENSE](LICENSE)。

---

<p align="center">
  <strong>Language / 语言</strong>：
  <a href="#english">↑ English</a> · <a href="#中文">↑ 中文</a>
</p>

## Project identity and upgrades

The application is **Recharge AI-task**. Its package and commands use
`recharge-ai-task`, and the Python package is `recharge_ai_task`.
Run `recharge-ai-task gui` or `recharge-ai-task-gui` for the dashboard.

Settings now live in `~/.recharge-ai-task/config.json`. On the first default
launch, existing settings from the previous name are copied byte for byte;
existing new settings are never overwritten and the original remains a backup.
Explicit `RECHARGE_AI_TASK_CONFIG_DIR` paths stay isolated. The previous
configuration and language environment variables are accepted during upgrades,
with the new variables taking precedence. Startup registration uses
`recharge-ai-task-tray.desktop` on Linux or `recharge-ai-task-tray.bat` on Windows;
enabling or disabling startup also retires its previous registration.

The GitHub repository is
[Recharge AI-task](https://github.com/mikkovedru/recharge-ai-task).
Use `origin` for this repository and `upstream` for
[Autumnpoem's original project](https://github.com/Autumnpoem/codex-autocontinue).
Development and releases use the `master` branch.

## Linux Mint Cinnamon

The tray uses the blue 5h recharge logo on an opaque white background with a dark border and a yellow (idle) or green (running) status strip. When Cinnamon's native XApp status applet is active, it uses XApp; with legacy or collapsible trays it uses an opaque XEmbed drawing surface at the actual allocated size, avoiding GTK StatusIcon caches and clipping. Image paths bypass symbolic icon recoloring; status is also shown by the tooltip and bottom color strip. Both left and right clicks open the menu. Cinnamon still controls the panel's icon size and whether its XApp status applet is visible.

```bash
sudo apt install python3-venv python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-3.0 gir1.2-xapp-1.0 python3-pyatspi gir1.2-atspi-2.0 xdotool
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e ".[tray,dev]"
PYTHON=.venv/bin/python bash scripts/build_linux.sh
./dist/recharge-ai-task-tray
```

Alternatively, run from source with `bash scripts/run_tray.sh`. The launcher works from any directory. Use `RECHARGE_AI_TASK_CONFIG_DIR` for isolated settings during checks; live quota tests require `RECHARGE_AI_TASK_LIVE_TESTS=1`. `PYSTRAY_BACKEND` can explicitly override the Cinnamon backend selection.


## Choose Codex signal recipients

The tray menu now has **Open Recharge AI-task…**. Select one or several chats or
windows; checkbox and prompt changes save automatically for quota-reset signals.
The picker shows titles,
thread/window IDs, process IDs, profiles, deep links, projects and live desktop
owners. Chat targets address a stable ID; window targets use the chat and focused
input currently shown in that window.

```bash
./dist/recharge-ai-task gui
./dist/recharge-ai-task-gui
./dist/recharge-ai-task targets --gui
./dist/recharge-ai-task targets --json
./dist/recharge-ai-task targets --select THREAD_ID_1 --select THREAD_ID_2
```

After installing the Python package, use `recharge-ai-task gui` or `recharge-ai-task-gui`.
For a release archive, keep all three executables together. `recharge-ai-task --help`
lists both GUI commands. GUI launch commands also start the tray, or reuse the
running tray and bring its dashboard forward. Closing the window keeps the tray
and its watch available. Double-click the tray icon to hide the open dashboard
to the tray or restore it, preserving the current view. Right-click for the tray menu. Use **Exit** in that menu to quit the application.

The GUI saves checkbox and multiline prompt edits automatically, and shows
task and goal status refreshed every 15 seconds,
live quota usage and reset countdowns,
startup registration and launch origin, and the actual Desktop watch state.
Use **Start/Stop Desktop watch** and **Settings…** directly from this window.
Each row has independent **Prompt** and **Goal** checkboxes. Use **Send signals**
for an immediate send; the choices also persist for quota-reset delivery:

- **Prompt** sends only the configured prompt message.
- **Goal** verifies native activation and continues the goal without a user prompt.
- **Both** verifies Goal activation first, then sends the prompt to continue work.
- **Neither** excludes the recipient. Window recipients support Prompt only.

Goal activation preserves the existing objective, budget and usage history.
Manual sends may resume paused goals even while a prompt turn is running,
without adding a competing empty turn; automatic quota recovery respects intentional
pauses and skips blocked, completed, budget-limited or already-running goals.
An independently selected Prompt still sends when the Goal action is skipped;
a failed or unconfirmed Goal action prevents the subsequent prompt. Results for
each recipient appear in the window. Starting watch after quota has recovered
also recovers selected usage-limited goals, after the grace period.
The checkbox before **Run at login** enables or disables startup directly;
the watch button is beside its **Desktop watch: On/Off** status, bordered green
when On, red when Off, and yellow while Stopping. **Refresh** sits directly
below the list; **Copy link / ID** and **Open selected row** are on its right.
The recipient summary and **Send signals** sit below the multiline prompt, with
the send button on the far right. **Project** shows the name assigned in Codex;
**Project path** retains the chat's working path. Both precede **Kind**.
Old selections migrate to Prompt, or Prompt + Goal when old goal recovery was enabled.
Saved changes automatically restart an active watch after a short debounce.
The previous worker finishes first, and quota-reset delivery accounting is
preserved. Empty selections or blank Prompt drafts suspend it until valid;
explicitly stopping the watch cancels pending restarts.

Choose targets before starting desktop watch. Local saved chats are included;
account-wide ChatGPT history and disconnected remote hosts are not enumerated.
See [the research, design and delivery notes](docs/target-selection.md) for protocol
compatibility, focus requirements and per-target retry behavior.
