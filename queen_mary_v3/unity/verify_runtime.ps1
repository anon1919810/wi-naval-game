param(
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [string]$UnityExe = 'D:/Unity/Editor/2022.3.62f3c1/Editor/Unity.exe',
    [string]$OutputDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'runtime_acceptance'),
    [switch]$Benchmark
)
$ErrorActionPreference = 'Stop'
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

function Run-UnityTask([string]$Method, [string]$Destination, [string]$Label) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $arguments = @('-batchmode', '-projectPath', $ProjectPath, '-executeMethod', $Method,
        '-shipReportDirectory', $Destination, '-logFile', (Join-Path $Destination "$Label.log"))
    # Start-Process joins ArgumentList on Windows; quote path arguments explicitly.
    $quoted = $arguments | ForEach-Object {
        if ($_.Contains('"')) { throw 'Double quotes are not allowed inside task paths.' }
        '"' + $_ + '"'
    }
    $taskProcess = Start-Process -FilePath $UnityExe -ArgumentList $quoted -WindowStyle Hidden -PassThru
    $taskProcess.WaitForExit()
    if ($taskProcess.ExitCode -ne 0) { throw "$Label failed (exit $($taskProcess.ExitCode)); see $Destination/$Label.log" }
}

& (Join-Path $PSScriptRoot 'sync_to_unity.ps1') -ProjectPath $ProjectPath
Run-UnityTask 'Naval.EditorTools.ShipRuntimeAcceptance.RebuildAndTestBatch' $OutputDirectory 'acceptance'
Run-UnityTask 'Naval.EditorTools.ShipDeliveryChecks.RunBatch' $OutputDirectory 'delivery'
$acceptance = Get-Content -LiteralPath (Join-Path $OutputDirectory 'runtime_acceptance.json') -Raw | ConvertFrom-Json
if ($acceptance.status -ne 'passed') { throw 'Runtime acceptance failed.' }

if ($Benchmark) {
    $benchmarkDirectory = Join-Path $OutputDirectory 'benchmark'
    Run-UnityTask 'Naval.EditorTools.ShipBenchmarkBuilder.BuildBatch' $benchmarkDirectory 'build_player'
    $player = Join-Path $benchmarkDirectory 'player/QueenMaryFleetBenchmark.exe'
    $results = Join-Path $benchmarkDirectory 'results'
    New-Item -ItemType Directory -Path $results -Force | Out-Null
    $playerArguments = @('-screen-fullscreen','0','-screen-width','1920','-screen-height','1080',
        '-shipReportDirectory', ('"' + $results + '"'), '-logFile', ('"' + (Join-Path $results 'player.log') + '"'))
    $playerProcess = Start-Process -FilePath $player -ArgumentList $playerArguments -WindowStyle Hidden -PassThru
    $playerProcess.WaitForExit()
    if ($playerProcess.ExitCode -ne 0) { throw "Benchmark player failed: $($playerProcess.ExitCode)" }
    $report = Get-Content -LiteralPath (Join-Path $results 'fleet_benchmark.json') -Raw | ConvertFrom-Json
    if ($report.status -ne 'completed') { throw 'Benchmark did not finish all five stages.' }
}
Write-Output "Ship runtime checks passed. Reports: $OutputDirectory"
