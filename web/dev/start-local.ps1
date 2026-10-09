#Requires -Version 7.4
<# Start the loopback UI preview. Requires an existing migrated SQLite database.
   Never creates/migrates databases, kills processes, or changes environment settings.
   Run from the repository root: pwsh -File web/dev/start-local.ps1
#>
[CmdletBinding()]
param([string]$DatabasePath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$RunDir = Join-Path $RepoRoot '.superpowers/sdd/local-preview-2026-10-08'
$Python = Join-Path $RepoRoot 'web/backend/.venv/Scripts/python.exe'
$Bootstrap = Join-Path $PSScriptRoot 'anonymous_api.py'
$Frontend = Join-Path $RepoRoot 'web/frontend'
$ApiOrigin = 'http://127.0.0.1:8000'
$WebOrigin = 'http://127.0.0.1:5173'
$ExplicitDatabase = $PSBoundParameters.ContainsKey('DatabasePath')
if (-not $DatabasePath) {
    $DatabasePath = Join-Path $RepoRoot '.superpowers/sdd/advanced-workflow-plan-2026-10-04/browser-check.db'
}
$DatabasePath = [IO.Path]::GetFullPath($DatabasePath)

foreach ($file in @($Python, $Bootstrap, $DatabasePath, (Join-Path $Frontend 'node_modules/vite/bin/vite.js'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required local file missing: $file" }
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm.cmd is not on PATH.' }
& $Python $Bootstrap --database $DatabasePath --check-only
if ($LASTEXITCODE -ne 0) { throw 'Existing database validation failed; nothing was started.' }

function Read-Json([string]$Url) {
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec 2 | ConvertTo-Json -Compress | ConvertFrom-Json -AsHashtable }
    catch { return $null }
}
function Test-Api([string]$Origin) {
    $health = Read-Json "$Origin/api/health"
    $config = Read-Json "$Origin/api/auth/config"
    return ($null -ne $health -and $health['service'] -eq 'plimsoll-web' -and
        $health['status'] -eq 'ok' -and $null -ne $config -and $config['mode'] -eq 'anonymous')
}
function Test-Web {
    try {
        $page = Invoke-WebRequest -Uri $WebOrigin -TimeoutSec 2 -UseBasicParsing
        return ($page.Content -match 'Formfield' -and $page.Content -match '/src/main.tsx' -and $page.Content -match '/@vite/client')
    } catch { return $false }
}
function Assert-FreePort([int]$Port) {
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count) { throw "Port $Port is occupied by an unrecognised or unhealthy service. Nothing was stopped." }
}
function Wait-Ready([scriptblock]$Check, [Diagnostics.Process]$Process, [string]$Name, [string]$ErrorLog) {
    $deadline = (Get-Date).AddSeconds(25)
    do {
        if (& $Check) { return }
        $Process.Refresh()
        if ($Process.HasExited) { throw "$Name exited. See $ErrorLog" }
        Start-Sleep -Milliseconds 350
    } while ((Get-Date) -lt $deadline)
    throw "$Name did not become ready within 25 seconds. See $ErrorLog"
}

$apiUp = Test-Api $ApiOrigin
$webUp = Test-Web
if ($apiUp -and $ExplicitDatabase) {
    throw 'An API is already running. Its database cannot be changed or verified by this command. Stop it before supplying -DatabasePath.'
}
# Check both ports before starting either process.
if (-not $apiUp) { Assert-FreePort 8000 }
if (-not $webUp) { Assert-FreePort 5173 }
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

if ($apiUp) {
    Write-Host 'API reused; its existing database and sessions are retained.'
} else {
    $apiError = Join-Path $RunDir 'api.stderr.log'
    $api = Start-Process -FilePath $Python -ArgumentList @('-u', "`"$Bootstrap`"", '--database', "`"$DatabasePath`"") `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $RunDir 'api.stdout.log') -RedirectStandardError $apiError
    Set-Content -LiteralPath (Join-Path $RunDir 'api.pid') -Value $api.Id
    Wait-Ready { Test-Api $ApiOrigin } $api 'API' $apiError
    Write-Host "API started (launcher PID $($api.Id))."
}
if ($webUp) {
    Write-Host 'Vite reused on 127.0.0.1:5173.'
} else {
    $webError = Join-Path $RunDir 'web.stderr.log'
    $web = Start-Process -FilePath $env:ComSpec `
        -ArgumentList '/d', '/c', 'npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort' `
        -WorkingDirectory $Frontend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $RunDir 'web.stdout.log') -RedirectStandardError $webError
    Set-Content -LiteralPath (Join-Path $RunDir 'web.pid') -Value $web.Id
    Wait-Ready { Test-Web } $web 'Vite' $webError
    Write-Host "Vite started (launcher PID $($web.Id))."
}
if (-not (Test-Api $WebOrigin)) { throw 'Vite is serving, but its /api proxy did not pass the anonymous API check.' }
Write-Host "Preview ready: $WebOrigin/#/work"
Write-Host "Logs: $RunDir"
Write-Host 'UI preview only. Calculations need a separate worker; see docs/plimsoll-1.0/web-local-operations.md.'
