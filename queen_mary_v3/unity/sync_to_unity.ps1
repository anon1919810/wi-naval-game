param(
    [Parameter(Mandatory = $true)][string]$ProjectPath
)

# 把资产与 Unity 侧代码同步进工程。路径全部从 $PSScriptRoot 推导，
# 不在脚本里写中文绝对路径（.ps1 含非 ASCII 路径会因编码问题静默出错）。
#
# 本脚本位于 <资产目录>\unity\ 下，所以**资产目录就是它的上一级** ——
# 融合之后只有一个家（queen_mary_v3/unity），不要再写死某个版本目录名。

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$assetDir = Split-Path $here -Parent
$shipId = 'HMS_Queen_Mary_1913'

if (-not (Test-Path $ProjectPath)) { throw "工程不存在：$ProjectPath" }
$versionFile = Join-Path $ProjectPath 'ProjectSettings/ProjectVersion.txt'
if (-not (Test-Path $versionFile)) { throw "这不是 Unity 工程（缺 ProjectSettings/ProjectVersion.txt）：$ProjectPath" }
if (-not (Test-Path $assetDir)) { throw "找不到资产目录：$assetDir" }

Write-Host "Unity 版本：" (Get-Content $versionFile -TotalCount 1)
Write-Host "资产目录：$assetDir"

$destShip = Join-Path $ProjectPath "Assets/Resources/Ships/$shipId"
$destScripts = Join-Path $ProjectPath 'Assets/Scripts/Naval'
$destEditor = Join-Path $ProjectPath 'Assets/Editor'
foreach ($d in @($destShip, $destScripts, $destEditor)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

# 1) Unity 侧代码
Copy-Item (Join-Path $here 'Assets/Scripts/Naval/ShipContract.cs') $destScripts -Force
foreach ($f in @('ShipModelImportSettings.cs', 'ShipAssetValidator.cs', 'AxisProbe.cs',
                 'UrpSetup.cs', 'ShipMaterialRemap.cs', 'ShipPreviewRender.cs')) {
    $src = Join-Path $here "Assets/Editor/$f"
    if (Test-Path $src) { Copy-Item $src $destEditor -Force }
}
Write-Host "已同步 Editor 脚本：ShipModelImportSettings / ShipAssetValidator / AxisProbe / UrpSetup / ShipMaterialRemap / ShipPreviewRender"

# 2) 资产本体：FBX + 全部 JSON
$required = @("$shipId`_Greybox.fbx", 'ship_contract.unity.json')
$optional = @('object_manifest.json', 'damage_model.json', 'hydrostatics.json',
              'buoyancy_compartments.json', 'firing_arcs.json', 'ship_contract.json')
$missing = @()
foreach ($f in $required) {
    $src = Join-Path $assetDir $f
    if (-not (Test-Path $src)) { $missing += $f; continue }
    Copy-Item $src $destShip -Force
}
foreach ($f in $optional) {
    $src = Join-Path $assetDir $f
    if (Test-Path $src) { Copy-Item $src $destShip -Force }
}
if ($missing.Count -gt 0) { throw "缺少必需文件：$($missing -join ', ')" }

Write-Host "已同步到 $destShip ："
Get-ChildItem $destShip -File | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "回到 Unity 等导入完成（Console 先确认没有编译错误），然后跑菜单 Tools > Naval > Validate ship asset"
