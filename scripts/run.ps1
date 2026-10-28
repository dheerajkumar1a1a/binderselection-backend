<#
.SYNOPSIS
    Start the Binder Selection Agent (production web app) on Windows.

.DESCRIPTION
    Runs prod.web:app with uvicorn from .venv. Defaults to 127.0.0.1:8123,
    which is reachable only from this machine.

.PARAMETER Port
    TCP port. Default 8123.

.PARAMETER Dev
    Enable auto-reload for Python, templates and static files. Use while
    editing; do NOT use for a demo (a reload mid-flow drops in-flight work).

.PARAMETER Lan
    Bind 0.0.0.0 so other machines on the network can connect. Read the
    warning it prints first - the seeded passwords are change-me-*.

.EXAMPLE
    .\scripts\run.ps1

.EXAMPLE
    .\scripts\run.ps1 -Dev -Port 9000
#>
[CmdletBinding()]
param(
    [int]$Port = 8123,
    [switch]$Dev,
    [switch]$Lan
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "No .venv found. Run .\scripts\bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}

$bind = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
if ($Lan) {
    Write-Host "WARNING: binding 0.0.0.0 exposes this app to your local network." -ForegroundColor Yellow
    Write-Host "The seeded passwords are change-me-*. Change them at /admin/users first." -ForegroundColor Yellow
    Write-Host ""
}

$arguments = @("-m", "uvicorn", "prod.web:app", "--host", $bind, "--port", "$Port")
if ($Dev) {
    $arguments += "--reload"
    Write-Host "Dev mode: Python, templates and static files reload on change." -ForegroundColor DarkGray
}

Write-Host "Binder Selection Agent -> http://$($bind):$Port" -ForegroundColor Cyan
Write-Host "Sign in at /login. Stop with Ctrl+C."
Write-Host ""

& $venvPython @arguments
