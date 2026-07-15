# Build standalone Windows x86_64 executables for codex-charge.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ([Environment]::Is64BitOperatingSystem -ne $true) {
    Write-Error "Release builds target x86_64 Windows only."
}

$Locales = Join-Path $Root "codex_charge\locales"
$CommonArgs = @(
    "--noconfirm", "--onefile",
    "--paths", $Root,
    "--collect-submodules", "codex_charge",
    "--collect-data", "codex_charge",
    "--add-data", "$Locales;codex_charge\locales"
)

Write-Host "Building codex-charge CLI..."
pyinstaller @CommonArgs --console `
  --name codex-charge `
  --collect-all winpty `
  scripts/entry_cli.py

Write-Host "Building codex-charge tray app..."
pyinstaller @CommonArgs --windowed `
  --name codex-charge-tray `
  --collect-all winpty `
  --collect-all pystray `
  scripts/entry_tray.py

Write-Host ""
Write-Host "Output:"
Write-Host "  dist\codex-charge.exe"
Write-Host "  dist\codex-charge-tray.exe"
Write-Host ""
Write-Host "Copy both EXEs to the same folder before using the tray app."
