param(
    [string]$BlenderExe = "$env:LOCALAPPDATA/Microsoft/WindowsApps/blender-launcher.exe",
    [switch]$SkipRender
)
$ErrorActionPreference = 'Stop'
$qmStarted = [DateTimeOffset]::UtcNow.AddSeconds(-1)
$qmArguments = @('--background','--factory-startup','--python-exit-code','1',
    '--python',(Join-Path $PSScriptRoot 'queen_mary_v4.py'),'--','--out',$PSScriptRoot)
if ($SkipRender) { $qmArguments += '--skip-render' }
& $BlenderExe @qmArguments
$qmDeadline = [DateTimeOffset]::UtcNow.AddMinutes(20)
$qmResult = Join-Path $PSScriptRoot 'build_result.json'
$qmFresh = $false
while ([DateTimeOffset]::UtcNow -lt $qmDeadline) {
    if (Test-Path -LiteralPath $qmResult) {
        $qmData = Get-Content -LiteralPath $qmResult -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([DateTimeOffset]::Parse($qmData.started_utc) -ge $qmStarted) {
            if ($qmData.status -eq 'failed') { throw $qmData.traceback }
            if ($qmData.status -eq 'complete') { $qmFresh = $true; break }
        }
    }
    Start-Sleep -Milliseconds 500
}
if (-not $qmFresh) { throw 'No fresh Blender completion report. Check the selected Blender executable.' }
foreach ($qmName in @('QueenMary_v4_Full.blend','QueenMary_v4_Cutaway.blend','QueenMary_v4_Exterior.fbx','QueenMary_v4_Interior.fbx','QueenMary_v4_Gameplay.fbx')) {
    $qmFile = Get-Item -LiteralPath (Join-Path $PSScriptRoot $qmName)
    if ($qmFile.Length -lt 1024 -or $qmFile.LastWriteTimeUtc -lt $qmStarted.UtcDateTime) { throw "Missing or stale output: $qmName" }
}
$qmVerifyStart = [DateTime]::UtcNow.AddSeconds(-1)
& $BlenderExe --background --factory-startup --python-exit-code 1 --python (Join-Path $PSScriptRoot 'verify_v4.py') -- --asset-dir $PSScriptRoot
$qmVerifyFile = Get-Item -LiteralPath (Join-Path $PSScriptRoot 'verification_v4_independent.json')
$qmVerify = Get-Content -LiteralPath $qmVerifyFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
if ($qmVerifyFile.LastWriteTimeUtc -lt $qmVerifyStart -or $qmVerify.status -ne 'passed') { throw 'Independent verification failed or stale.' }
Write-Output "v4 verified: $($qmVerify.passed_checks)/$($qmVerify.total_checks). $PSScriptRoot"
