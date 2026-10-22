# Package Windows release zip from dist/ artifacts.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$cli = Join-Path $Root "dist\recharge-ai-task-cli.exe"
$gui = Join-Path $Root "dist\recharge-ai-task.exe"
$legacyGui = Join-Path $Root "dist\recharge-ai-task-gui.cmd"
$tray = Join-Path $Root "dist\recharge-ai-task-tray.cmd"
$out = Join-Path $Root "dist\recharge-ai-task-windows-x86_64.zip"

if (-not (Test-Path $cli)) { throw "Missing $cli — run scripts/build_windows.ps1 first" }
if (-not (Test-Path $gui)) { throw "Missing $gui — run scripts/build_windows.ps1 first" }
if (-not (Test-Path $tray)) { throw "Missing $tray — run scripts/build_windows.ps1 first" }

if (-not (Test-Path $legacyGui)) { throw "Missing $legacyGui — run scripts/build_windows.ps1 first" }

if (Test-Path $out) { Remove-Item $out -Force }

Compress-Archive -Path $cli, $gui, $legacyGui, $tray -DestinationPath $out -Force

$hash = (Get-FileHash $out -Algorithm SHA256).Hash.ToLower()
Write-Host ""
Write-Host "Created: $out"
Write-Host "SHA256:  $hash"
Write-Host ""
Write-Host "Upload to GitHub Release as: recharge-ai-task-windows-x86_64.zip"
