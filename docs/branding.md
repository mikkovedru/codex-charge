# Project artwork

<p align="center">
  <img src="assets/logo-lockup.png" width="320" alt="Recharge AI-task logo">
</p>

Use the text-free blue **5h recharge** symbol for application and tray icons.
Use the logo with the project name in documentation and the dashboard.
The checked-in assets are resized copies of the approved artwork; documentation
and program code use these assets rather than the original input files.

| Location | Purpose | Size |
|----------|---------|------|
| `docs/assets/logo-lockup.png` | Documentation logo with project name | 512 × 512 |
| `recharge_ai_task/assets/logo-lockup.png` | Dashboard logo | 128 × 128 |
| `recharge_ai_task/assets/logo-symbol.png` | Tray source artwork | 512 × 512 |
| `recharge_ai_task/assets/icon-*.png` | Window and desktop icons | 16, 24, 32, 48, 64, 128, 256 px |
| `recharge_ai_task/assets/recharge-ai-task.ico` | Windows executable icon | 16–256 px in one ICO |

`branding.py` supplies the shared tray, window and desktop artwork. The tray
adds an opaque background, dark outer edge and colored status strip.
These stay visible on light and dark panels without relying on theme colors.
The tooltip also states the status. Desktop startup entries use a persistent
copy of the icon, so the icon survives a one-file executable exiting.

To regenerate the assets with Pillow installed:

```bash
python scripts/prepare_branding.py --symbol /path/to/symbol.png --lockup /path/to/logo-with-name.png
```

Python packages and frozen executables include runtime assets automatically.
The Windows build uses the ICO for the CLI and combined desktop executable shell icons.
