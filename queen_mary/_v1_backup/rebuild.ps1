param(
    [string]$BlenderExe = "$env:LOCALAPPDATA/Microsoft/WindowsApps/blender-launcher.exe",
    [switch]$SkipRender
)
$ErrorActionPreference = 'Stop'
$qmStart = [DateTimeOffset]::UtcNow.AddSeconds(-2)
$qmBuildArgs = @('--background','--factory-startup','--python-exit-code','1',
    '--python',(Join-Path $PSScriptRoot 'queen_mary.py'),'--','--out',$PSScriptRoot,'--check-repeat')
if ($SkipRender) { $qmBuildArgs += '--skip-render' }
& $BlenderExe @qmBuildArgs

# Store launcher stdout/exit code is insufficient. Check a fresh completion record.
$qmDeadline = [DateTimeOffset]::UtcNow.AddMinutes(3)
$qmResultPath = Join-Path $PSScriptRoot 'build_result.json'
$qmFresh = $false
while ([DateTimeOffset]::UtcNow -lt $qmDeadline) {
    if (Test-Path -LiteralPath $qmResultPath) {
        $qmReport = Get-Content -LiteralPath $qmResultPath -Raw | ConvertFrom-Json
        if ([DateTimeOffset]::Parse($qmReport.started_utc) -ge $qmStart) {
            if ($qmReport.status -eq 'failed') { throw $qmReport.traceback }
            if ($qmReport.status -eq 'complete') { $qmFresh = $true; break }
        }
    }
    Start-Sleep -Milliseconds 500
}
if (-not $qmFresh) { throw 'Blender produced no fresh completion record. Check Store activation.' }
foreach ($qmName in @('HMS_Queen_Mary_1913_Greybox.blend','HMS_Queen_Mary_1913_Greybox.fbx')) {
    $qmArtifact = Get-Item -LiteralPath (Join-Path $PSScriptRoot $qmName)
    if ($qmArtifact.LastWriteTimeUtc -lt $qmStart.UtcDateTime -or $qmArtifact.Length -lt 1000) {
        throw "Artifact is stale or empty: $qmName"
    }
}
$qmCheckStart = [DateTime]::UtcNow.AddSeconds(-2)
& $BlenderExe --background (Join-Path $PSScriptRoot 'HMS_Queen_Mary_1913_Greybox.blend') --python-exit-code 1 --python (Join-Path $PSScriptRoot 'verify_blender.py')
& $BlenderExe --background --factory-startup --python-exit-code 1 --python (Join-Path $PSScriptRoot 'verify_fbx.py')
$qmSceneFile = Get-Item -LiteralPath (Join-Path $PSScriptRoot 'verification.json')
$qmFbxFile = Get-Item -LiteralPath (Join-Path $PSScriptRoot 'fbx_verification.json')
if ($qmSceneFile.LastWriteTimeUtc -lt $qmCheckStart -or $qmFbxFile.LastWriteTimeUtc -lt $qmCheckStart) {
    throw 'Verification reports are stale.'
}
$qmChecks = Get-Content -LiteralPath $qmSceneFile.FullName -Raw | ConvertFrom-Json
$qmFbxChecks = Get-Content -LiteralPath $qmFbxFile.FullName -Raw | ConvertFrom-Json
if (@($qmChecks | Where-Object { -not $_.passed }).Count -gt 0 -or $qmFbxChecks.status -ne 'passed') {
    throw 'Model verification failed. Read verification.json and fbx_verification.json.'
}
Write-Output "Queen Mary build verified: $($qmChecks.Count) scene checks, $($qmFbxChecks.checks.Count) FBX checks."
Write-Output "Output: $PSScriptRoot"
