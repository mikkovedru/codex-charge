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
    "--paths", $Root,
    "--collect-submodules", "recharge_ai_task",
    "--collect-data", "recharge_ai_task",
    "--icon", (Join-Path $Root "recharge_ai_task\assets\recharge-ai-task.ico"),
    "--add-data", "$Locales;recharge_ai_task\locales"
)

Write-Host "Building recharge-ai-task CLI..."
pyinstaller @CommonArgs --console `
  --name recharge-ai-task `
  --collect-all winpty `
  scripts/entry_cli.py

Write-Host "Building recharge-ai-task tray app..."
pyinstaller @CommonArgs --windowed `
  --name recharge-ai-task-tray `
  --collect-all winpty `
  --collect-all pystray `
  scripts/entry_tray.py

Write-Host ""
Write-Host "Output:"
Write-Host "  dist\recharge-ai-task.exe"
Write-Host "  dist\recharge-ai-task-tray.exe"
Write-Host ""
Write-Host "Copy both EXEs to the same folder before using the tray app."
