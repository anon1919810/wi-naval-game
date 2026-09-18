param(
    [Parameter(Mandatory = $true)][string]$ProjectPath
)

# 把资产与 Unity 侧代码同步进工程。路径全部从 $PSScriptRoot 推导，
# 不在脚本里写中文绝对路径（.ps1 含非 ASCII 路径会因编码问题静默出错）。
#
# 本脚本位于 <资产目录>\unity\ 下，所以**资产目录就是它的上一级** ——
# 融合之后只有一个家（queen_mary_v3/unity），不要再写死某个版本目录名。
#
# 目录映射（融合后的实际结构）：
#   unity/Editor/*.cs   ->  Assets/Editor/
#   unity/Scripts/*.cs  ->  Assets/Scripts/Naval/
#   <资产目录>/*.fbx     ->  Assets/Resources/Ships/<shipId>/   （名字从契约读）
#   <资产目录>/*.json    ->  Assets/Resources/Ships/<shipId>/   （清单从契约读）
#
# 两条纪律：
#  ① **不维护 .cs 白名单** —— 整目录按扩展名拷。白名单必然漂（加一个工具就忘一次）。
#  ② **FBX 名字从契约的 file_refs.fbx 读**，不硬编码：v2 叫 *_Greybox.fbx、v3 叫
#     *_Refined_v3.fbx，硬编码换一代就断。

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

# ---------------------------------------------------------------- 1) C# 代码
$editorSrc = Join-Path $here 'Editor'
$scriptsSrc = Join-Path $here 'Scripts'
if (-not (Test-Path $editorSrc)) { throw "找不到 Editor 目录：$editorSrc" }
if (-not (Test-Path $scriptsSrc)) { throw "找不到 Scripts 目录：$scriptsSrc" }

Copy-Item (Join-Path $scriptsSrc '*.cs') $destScripts -Force
Copy-Item (Join-Path $editorSrc '*.cs') $destEditor -Force
$editorCount = @(Get-ChildItem (Join-Path $editorSrc '*.cs')).Count
$scriptCount = @(Get-ChildItem (Join-Path $scriptsSrc '*.cs')).Count
Write-Host "已同步代码：Editor $editorCount 个 .cs / Scripts $scriptCount 个 .cs"

# ------------------------------------------------------- 2) 契约（清单来源）
$contractSrc = Join-Path $assetDir 'ship_contract.unity.json'
if (-not (Test-Path $contractSrc)) { throw "找不到契约：$contractSrc" }

$fbxName = $null
$dataNames = New-Object System.Collections.Generic.List[string]
try {
    $json = Get-Content $contractSrc -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($ref in $json.file_refs) {
        $leaf = Split-Path $ref.path -Leaf
        if ($ref.key -eq 'fbx') { $fbxName = $leaf } else { $dataNames.Add($leaf) }
    }
} catch {
    Write-Warning ("契约解析失败，将退回按扩展名查找：" + $_.Exception.Message)
}

if (-not $fbxName) {
    $cand = Get-ChildItem (Join-Path $assetDir '*.fbx') |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($cand) { $fbxName = $cand.Name; Write-Warning "契约里没有 fbx 条目，按最新 .fbx 取：$fbxName" }
}
if (-not $fbxName) { throw "资产目录里没有任何 .fbx" }

# buoyancy_compartments.json 是 ShipRuntimeBuilder 的必需输入，但**契约的 file_refs 里没有它**
# —— 契约那侧应该补一行。在补上之前这里显式带上，否则舱室会全部拿不到浮力数据。
$dataNames.Add('ship_contract.unity.json')
$dataNames.Add('ship_contract.json')
$dataNames.Add('buoyancy_compartments.json')
$dataNames.Add('lod_profiles.json')
$dataNames.Add('firing_arcs.json')
$dataNames.Add('firing_arcs.unity.json')

$copied = @()
$missing = @()
foreach ($name in ($dataNames | Sort-Object -Unique)) {
    $src = Join-Path $assetDir $name
    if (Test-Path $src) { Copy-Item $src $destShip -Force; $copied += $name }
    else { $missing += $name }
}

$fbxSrc = Join-Path $assetDir $fbxName
if (-not (Test-Path $fbxSrc)) { throw "FBX 不存在：$fbxSrc" }
Copy-Item $fbxSrc $destShip -Force

# ------------------------------------------------------------- 3) 收尾自检
# 契约没进工程 = 后面所有工具都读不到，必须在这里拦住（别等 Unity 里报一堆错才发现）。
$contractDst = Join-Path $destShip 'ship_contract.unity.json'
if (-not (Test-Path $contractDst)) { throw "契约没拷进工程，同步失败" }
$fbxDst = Join-Path $destShip $fbxName
if (-not (Test-Path $fbxDst)) { throw "FBX 没拷进工程，同步失败" }

Write-Host "FBX（来自契约 file_refs.fbx）：$fbxName"
Write-Host "数据文件 $($copied.Count) 份：$($copied -join ', ')"
if ($missing.Count -gt 0) {
    Write-Warning ("契约指向但资产目录里没有（已跳过）：" + ($missing -join ', '))
}

Write-Host "已同步到 $destShip ："
Get-ChildItem $destShip -File |
    Where-Object { $_.Extension -eq '.fbx' -or $_.Extension -eq '.json' } |
    Select-Object Name, Length | Format-Table -AutoSize

Write-Host "回到 Unity 等导入完成（先在 Console 确认没有编译错误），然后依次跑："
Write-Host "  Tools > Naval > Set up URP        （换过材质/管线时）"
Write-Host "  Tools > Naval > Build runtime ship"
Write-Host "  Tools > Naval > Validate ship asset"
