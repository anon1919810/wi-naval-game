# Sync v4 presentation assets into the Unity test project (acceptance path).
# Does not replace GameplayLab prefab by itself; acceptance + lab builder decide that.
param(
    [Parameter(Mandatory = $true)][string]$ProjectPath
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$assetRoot = Split-Path -Parent $here          # queen_mary_v3
$repoRoot = Split-Path -Parent $assetRoot      # HMS_Queen_Mary_...
$v4 = Join-Path $repoRoot 'queen_mary_v4'
if (-not (Test-Path $v4)) { throw "queen_mary_v4 not found: $v4" }
if (-not (Test-Path $ProjectPath)) { throw "Unity project missing: $ProjectPath" }

$dest = Join-Path $ProjectPath 'Assets/Resources/Ships/HMS_Queen_Mary_1913_v4'
$matSrc = Join-Path $v4 'textures'
$matDst = Join-Path $ProjectPath 'Assets/Materials/NavalV4'
foreach ($d in @($dest, $matDst)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

Copy-Item (Join-Path $v4 'QueenMary_v4_Exterior.fbx') $dest -Force
Copy-Item (Join-Path $v4 'QueenMary_v4_Interior.fbx') $dest -Force
if (Test-Path (Join-Path $v4 'QueenMary_v4_Gameplay.fbx')) {
    Copy-Item (Join-Path $v4 'QueenMary_v4_Gameplay.fbx') $dest -Force
}
Copy-Item (Join-Path $v4 'material_manifest.json') $dest -Force
Copy-Item (Join-Path $v4 'interior_modules.json') $dest -Force
Copy-Item (Join-Path $v4 'delivery_manifest.json') $dest -Force -ErrorAction SilentlyContinue
if (Test-Path $matSrc) { Copy-Item (Join-Path $matSrc '*') $matDst -Force }

# Also sync gameplay C# from this worktree's unity folder
$unitySrc = Join-Path $assetRoot 'unity'
$destScripts = Join-Path $ProjectPath 'Assets/Scripts/Naval'
$destEditor = Join-Path $ProjectPath 'Assets/Editor'
Copy-Item (Join-Path $unitySrc 'Scripts/*.cs') $destScripts -Force
Copy-Item (Join-Path $unitySrc 'Editor/*.cs') $destEditor -Force

Write-Host "v4 synced to $dest"
Get-ChildItem $dest -File | Select-Object Name, Length | Format-Table -AutoSize
