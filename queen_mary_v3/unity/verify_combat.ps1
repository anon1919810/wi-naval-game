param(
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [string]$UnityExe = 'D:/Unity/Editor/2022.3.62f3c1/Editor/Unity.exe',
    [string]$AssetPath = ''
)
$ErrorActionPreference = 'Stop'
if (-not $AssetPath) { $AssetPath = Split-Path -Parent $PSScriptRoot }
$runId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$reportPath = Join-Path $AssetPath "runtime_acceptance/combat_a/$runId"
New-Item -ItemType Directory -Path $reportPath -Force | Out-Null
$meta = @{
    runId = $runId
    startedUtc = (Get-Date).ToUniversalTime().ToString('o')
    gitHead = ''
    projectPath = $ProjectPath
    unityExe = $UnityExe
} | ConvertTo-Json
Set-Content -Path (Join-Path $reportPath 'run_meta.json') -Value $meta -Encoding UTF8

function Invoke-UnityTests([string]$platform, [string]$xmlName, [string]$logName) {
    $xml = Join-Path $reportPath $xmlName
    $log = Join-Path $reportPath $logName
    $argList = @('-batchmode','-projectPath',"`"$ProjectPath`"",'-runTests','-testPlatform',$platform,
        '-testResults',"`"$xml`"","-logFile","`"$log`"")
    $p = Start-Process -FilePath $UnityExe -ArgumentList $argList -WindowStyle Hidden -PassThru
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) { Write-Warning "$platform exit $($p.ExitCode)" }
    if (-not (Test-Path $xml)) { throw "$platform produced no XML at $xml" }
    $content = Get-Content $xml -Raw
    if ($content -notmatch 'result="(\w+)"') { throw "$platform XML missing result" }
    $result = $matches[1]
    if ($content -match 'total="(\d+)"') { $total = [int]$matches[1] } else { throw "$platform XML missing total" }
    if ($content -match 'failed="(\d+)"') { $failed = [int]$matches[1] } else { $failed = -1 }
    if ($total -le 0) { throw "$platform total tests is 0" }
    if ($failed -gt 0 -or $result -eq 'Failed') { throw "$platform tests failed (failed=$failed result=$result)" }
    Write-Host "$platform PASS total=$total failed=$failed runId=$runId"
    return @{ result = $result; total = $total; failed = $failed }
}

& (Join-Path $PSScriptRoot 'sync_to_unity.ps1') -ProjectPath $ProjectPath
$edit = Invoke-UnityTests 'EditMode' 'editmode.xml' 'editmode.log'
$play = Invoke-UnityTests 'PlayMode' 'playmode.xml' 'playmode.log'
Write-Host "verify_combat OK runId=$runId report=$reportPath"
