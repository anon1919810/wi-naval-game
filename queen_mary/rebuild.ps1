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

# Two layers: geometry blocks the build, historical assumptions only warn.
$qmScene = Get-Content -LiteralPath $qmSceneFile.FullName -Raw | ConvertFrom-Json
$qmFbxChecks = Get-Content -LiteralPath $qmFbxFile.FullName -Raw | ConvertFrom-Json
$qmGeometry = @($qmScene.checks | Where-Object { $_.layer -eq 'geometry' })
$qmAssumption = @($qmScene.checks | Where-Object { $_.layer -eq 'assumption' })
$qmBlockingFails = @($qmGeometry | Where-Object { -not $_.passed })
$qmSoftFails = @($qmAssumption | Where-Object { -not $_.passed })
if ($qmBlockingFails.Count -gt 0) {
    $qmBlockingFails | ForEach-Object { Write-Output ("FAIL: " + $_.check + " " + ($_.evidence | ConvertTo-Json -Compress)) }
    throw 'Geometry verification failed. Read verification.json.'
}
if ($qmFbxChecks.status -ne 'passed') {
    throw 'FBX verification failed. Read fbx_verification.json.'
}
foreach ($qmSoft in $qmSoftFails) { Write-Output ("assumption gap: " + $qmSoft.check) }
Write-Output "Queen Mary build verified: $($qmGeometry.Count) geometry checks, $($qmAssumption.Count) assumption checks, $($qmFbxChecks.checks.Count) FBX checks."
Write-Output "Output: $PSScriptRoot"
