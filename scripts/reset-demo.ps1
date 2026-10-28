<#
.SYNOPSIS
    Reset the Binder Selection Agent's local demo state on Windows.

.DESCRIPTION
    Default (safe) mode deletes data\ and .checkpoints.sqlite: the SQLite
    database, the session signing key and the mail outbox, plus stale engine
    checkpoints. The next boot re-seeds the three demo accounts.

    -All also deletes audit\, capacity\ledger.json and ui\demo-ledger.json, so
    the capacity ledger and audit trail start empty too. Use this only when
    you want a pristine demo.

    Nothing outside this repository is touched.

.PARAMETER All
    Also delete the audit trail, capacity ledger and UI demo ledger.

.PARAMETER Force
    Skip the interactive confirmation (for scripted resets).

.EXAMPLE
    .\scripts\reset-demo.ps1

.EXAMPLE
    .\scripts\reset-demo.ps1 -All -Force
#>
[CmdletBinding()]
param(
    [switch]$All,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$targets = @("data", ".checkpoints.sqlite")
if ($All) {
    $targets += @("audit", "capacity\ledger.json", "ui\demo-ledger.json")
}

$existing = @()
foreach ($t in $targets) {
    if (Test-Path (Join-Path $root $t)) {
        $existing += $t
    }
}

if ($existing.Count -eq 0) {
    Write-Host "Nothing to reset - local state is already clean." -ForegroundColor Green
    exit 0
}

Write-Host "This will permanently delete:" -ForegroundColor Yellow
foreach ($t in $existing) {
    Write-Host "  - $t"
}
Write-Host ""
Write-Host "data\ holds the SQLite database, the session key and the mail outbox."
if ($All) {
    Write-Host "-All also removes the audit trail, the capacity ledger and the UI demo ledger."
}

if (-not $Force) {
    Write-Host ""
    $answer = Read-Host "Type 'yes' to continue"
    if ($answer -ne "yes") {
        Write-Host "Cancelled - nothing was deleted."
        exit 1
    }
}

foreach ($t in $existing) {
    Remove-Item -Recurse -Force (Join-Path $root $t)
    Write-Host "deleted $t"
}

Write-Host ""
Write-Host "Reset complete." -ForegroundColor Green
Write-Host "Start the app with .\scripts\run.ps1"
Write-Host "First boot re-seeds the demo accounts and prints their passwords."
Write-Host "You will be signed out, because the session key was deleted."
