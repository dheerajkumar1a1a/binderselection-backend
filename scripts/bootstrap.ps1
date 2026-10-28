<#
.SYNOPSIS
    One-command setup for the Binder Selection Agent on Windows.

.DESCRIPTION
    Verifies Python 3.12, creates .venv, installs the pinned dependency set,
    and runs the test suite. Safe to run again - it reuses an existing .venv.

.PARAMETER SkipTests
    Skip the pytest run (useful on a slow machine; run it before trusting the box).

.PARAMETER PythonExe
    Path or name of a specific Python 3.12 executable, when 'py -3.12' and
    'python' are not the ones you want.

.EXAMPLE
    .\scripts\bootstrap.ps1

.EXAMPLE
    .\scripts\bootstrap.ps1 -SkipTests
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Fail([string]$message) {
    Write-Host ""
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

function Get-PythonLauncher {
    if ($PythonExe) {
        if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
            Fail "Python executable '$PythonExe' was not found."
        }
        return @{ Exe = $PythonExe; Pre = @() }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @{ Exe = "py"; Pre = @("-3.12") }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = "python"; Pre = @() }
    }
    Fail ("Python 3.12 not found. Install it first:`n" +
          "  winget install --id Python.Python.3.12 -e`n" +
          "Then open a NEW PowerShell window and re-run this script.")
}

function Invoke-Checked {
    param([hashtable]$Py, [string[]]$Arguments)
    $all = @()
    $all += $Py.Pre
    $all += $Arguments
    & $Py.Exe @all
    if ($LASTEXITCODE -ne 0) {
        Fail "Command failed: $($Py.Exe) $($all -join ' ')"
    }
}

Write-Host "== Binder Selection Agent - bootstrap ==" -ForegroundColor Cyan
Write-Host "Repo: $root"
Write-Host ""

$py = Get-PythonLauncher
$version = (& $py.Exe @($py.Pre + @("-c", "import sys;print('%d.%d'%sys.version_info[:2])")))
if ($version -ne "3.12") {
    Fail ("This project is pinned to Python 3.12; found $version.`n" +
          "Install 3.12:  winget install --id Python.Python.3.12 -e`n" +
          "Then re-run, or pass -PythonExe with a 3.12 interpreter.")
}
Write-Host "Python 3.12 OK"

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating .venv ..."
    Invoke-Checked $py @("-m", "venv", ".venv")
} else {
    $venvVersion = & $venvPython -c "import sys;print('%d.%d'%sys.version_info[:2])"
    if ($venvVersion -ne "3.12") {
        Fail ("The existing .venv uses Python $venvVersion. Delete the .venv " +
              "folder and re-run this script to rebuild it on 3.12.")
    }
    Write-Host "Reusing existing .venv"
}

Write-Host ""
Write-Host "Installing dependencies ..."
& $venvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed." }

$lock = Join-Path $root "requirements.lock.txt"
$req = if (Test-Path $lock) { "requirements.lock.txt" } else { "requirements.txt" }
Write-Host "Using $req"
& $venvPython -m pip install -r $req --quiet
if ($LASTEXITCODE -ne 0) { Fail "Dependency install failed. Scroll up for the pip error." }

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "Running the test suite (expect: 215 passed) ..."
    & $venvPython -m pytest tests -q
    if ($LASTEXITCODE -ne 0) {
        Fail "Tests failed. Do not proceed until the suite is green."
    }
}

Write-Host ""
Write-Host "Bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next:"
Write-Host "  .\scripts\run.ps1"
Write-Host ""
Write-Host "First boot prints three seeded accounts (change-me-* passwords)."
Write-Host "Full runbook: docs\RECREATE.md"
