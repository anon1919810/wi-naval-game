$ErrorActionPreference = 'Stop'
$resultPath = Join-Path $PSScriptRoot ('rerun_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $resultPath -Force | Out-Null
$playerPath = Join-Path $PSScriptRoot 'player/QueenMaryFleetBenchmark.exe'
$arguments = @('-screen-fullscreen','0','-screen-width','1920','-screen-height','1080',
    '-shipReportDirectory', ('"' + $resultPath + '"'), '-logFile', ('"' + (Join-Path $resultPath 'player.log') + '"'))
$benchmarkProcess = Start-Process -FilePath $playerPath -ArgumentList $arguments -WindowStyle Hidden -PassThru
$benchmarkProcess.WaitForExit()
if ($benchmarkProcess.ExitCode -ne 0) { throw "Benchmark failed. Read $resultPath/player.log" }
$report = Get-Content -LiteralPath (Join-Path $resultPath 'fleet_benchmark.json') -Raw | ConvertFrom-Json
if ($report.status -ne 'completed') { throw 'Benchmark did not complete all stages.' }
$report.stages | Select-Object mode,shipPixels,@{Name='P95_ms';Expression={$_.frame.p95Ms}}
Write-Output "Offscreen benchmark results: $resultPath"
