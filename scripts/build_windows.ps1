# Build standalone Windows x86_64 executables for recharge-ai-task.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ([Environment]::Is64BitOperatingSystem -ne $true) {
    Write-Error "Release builds target x86_64 Windows only."
}

$Locales = Join-Path $Root "recharge_ai_task\locales"
$CommonArgs = @(
    "--noconfirm", "--onefile",
    "--specpath", (Join-Path $Root "build"),
    "--paths", $Root,
    "--collect-submodules", "recharge_ai_task",
    "--collect-data", "recharge_ai_task",
    "--icon", (Join-Path $Root "recharge_ai_task\assets\recharge-ai-task.ico"),
    "--add-data", "$Locales;recharge_ai_task\locales"
)

Write-Host "Building recharge-ai-task CLI..."
pyinstaller @CommonArgs --console `
  --name recharge-ai-task-cli `
  --collect-all winpty `
  scripts/entry_cli.py

Write-Host "Building the combined recharge-ai-task desktop app..."
pyinstaller @CommonArgs --windowed `
  --name recharge-ai-task `
  --collect-all winpty `
  --collect-all pystray `
  scripts/entry_gui.py

# Retire the old generated tray binary and keep its command as a small script.
$OldTray = Join-Path $Root "dist\recharge-ai-task-tray.exe"
if (Test-Path $OldTray) { Remove-Item $OldTray -Force }
$OldGui = Join-Path $Root "dist\recharge-ai-task-gui.exe"
if (Test-Path $OldGui) { Remove-Item $OldGui -Force }
$GuiLauncher = Join-Path $Root "dist\recharge-ai-task-gui.cmd"
Set-Content -Path $GuiLauncher -Encoding ascii -Value '@echo off', '"%~dp0recharge-ai-task.exe" %*'
$TrayLauncher = Join-Path $Root "dist\recharge-ai-task-tray.cmd"
Set-Content -Path $TrayLauncher -Encoding ascii -Value '@echo off', '"%~dp0recharge-ai-task.exe" --tray %*'

Write-Host ""
Write-Host "Output:"
Write-Host "  dist\recharge-ai-task.exe"
Write-Host "  dist\recharge-ai-task-cli.exe"
Write-Host "  dist\recharge-ai-task-gui.cmd (compatibility launcher)"
Write-Host "  dist\recharge-ai-task-tray.cmd (compatibility launcher)"
Write-Host ""
Write-Host "Copy both EXEs to the same folder before using the tray app."
