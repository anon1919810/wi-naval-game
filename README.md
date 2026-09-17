# HMS Queen Mary · 一战英国战列巡洋舰游戏资产

一艘 **1913 年 9 月服役原状**的战列巡洋舰「玛丽王后号」，用一份 Python 脚本在 Blender 里程序化生成，
带多层自动验证，并已接入 Unity（URP）。

- **性质**：灰盒（greybox），**不是**经过考证的精确复原——`historically_certified: false` 写在数据里
- **用途场景**：中距 50–200 m 观察，同屏 10–30 艘
- **当前资产版本**：**v3**（`queen_mary_v3/`），101 对象 / 85 网格 / 31,164 三角面

## 文档与资料索引

> 本仓库于 2026-09-18 建立。**此前的历史无法重建**，仓库从那一刻开始记录；
> v2 的目录按原样保留，作为只读历史。

### 先读哪一份

| 你想做什么 | 读这个 |
|---|---|
| 接手干活 | 本文（根 `README.md`） |
| 搞清楚 Unity 侧怎么做 | `queen_mary_v3/unity/README_集成.md` |
| 看历史交接（v2 视角） | `交接文件_GPT6_2026-09-17.md`（开头有 v3 指针） |
| 看 v3 那一侧的接续说明 | `queen_mary_v3/交接_v3.md` |
| 查素材与待补图 | `HMS_Queen_Mary_精修素材清单.md` |

### 交接与说明文档

| 路径 | 状态 |
|---|---|
| `README.md` | **当前入口**：目录地图 / 跑法 / 改动约定 |
| `交接文件_GPT6_2026-09-17.md` | 历史：v2 的交接（架构约定与踩坑仍有效） |
| `queen_mary_v3/交接_v3.md` | v3 的接续说明（另一条产线写的） |
| `queen_mary_v3/unity/README_集成.md` | Unity 集成：URP / 契约 / 轴向 / 材质 / 像素校验 |
| `queen_mary_v3/docs/DeepSeek_v2_原交接.md`、`…_原说明.md` | 归档：v2 文档的副本 |
| `queen_mary_v3/docs/legacy_codex_unity/README.md` | 归档：另一套并行实现的留档说明（**不要拷进工程**） |
| `queen_mary_v3/参考素材/素材说明.md` | 三张参考图的说明 |

### 资产、代码与工程

| 路径 | 内容 |
|---|---|
| `queen_mary_v3/` | **当前资产 v3**：`.blend` / `.fbx` / 七份 JSON / `.py` / `rebuild.ps1` |
| `queen_mary_v3/unity/` | **唯一的 Unity 集成家**：Editor 工具、契约类、同步脚本 |
| `queen_mary/` | 只读历史：v2（98 对象）与其 45 项验证链 |
| `参考素材/`、`queen_mary_v3/参考素材/` | 三张参考图，**都不可作为确定证据** |
| `D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval` | Unity 工程（URP 14.0.12，2022.3.62f3c1） |
| `C:\Users\杨睿\Documents\Codex\2026-09-17\shi\outputs` | 另一条产线的原始输出（zip + 各版本目录） |

### 校验证据（全部由机器生成，别手改）

| 文件 | 谁产出 | 验什么 |
|---|---|---|
| `queen_mary_v3/verification.json` | Blender | 45 项（32 几何 + 13 史实） |
| `queen_mary_v3/fbx_verification.json` | Blender | 18 项 FBX 往返 |
| `queen_mary_v3/integration_verification.json` | Codex | v2 → v3 的基线继承与哈希 |
| `queen_mary_v3/ship_runtime_build.json` | Unity 构建器 | 关渲染 24 / 碰撞体 24 / 舱室 13 |
| `queen_mary_v3/unity_verification_urp.json` | Unity 校验器 | 契约 137 名 / 轴向 / 右舷 / URP 材质 |
| `queen_mary_v3/unity_render_check.json` | Unity 渲染校验 | 像素级：品红 / 黑屏 / 取景 |
| `queen_mary_v3/unity_verification.json` | Codex 的导入检查器 | 导入（另一套，别与上面那份混） |
| `queen_mary_v3/checksums_sha256.json` | Codex | 全目录哈希清单 |

### 预览图

- **Blender 侧 8 张**：`queen_mary_v3/{Overview,Whole_200m,Detail_50m,Starboard,Top,Bow,Stern_Aft,Stern_Detail}.png`
- **Unity / URP 侧 5 张**：`queen_mary_v3/unity_preview/{Overview,Starboard,Top,Bow,Stern_Aft}.png`

## 目录地图（融合后只有一个家）

| 路径 | 是什么 |
|---|---|
| **`queen_mary_v3/`** | **当前资产**：`.blend` / `.fbx` / 七份 JSON / 预览图 / `rebuild.ps1` / `verify_*.py` / `probe_axis_convention.py`（轴映射探针，自包含） |
| **`queen_mary_v3/unity/`** | **唯一的 Unity 集成家**：Editor 工具、契约类、同步脚本、`README_集成.md` |
| `queen_mary_v3/docs/legacy_codex_unity/` | 归档：另一条产线写的并行实现（**不要拷进工程**） |
| `queen_mary/` | 只读历史：v2 资产（98 对象）与其 45 项验证链 |
| `参考素材/` | 三张参考图，**都不可作为确定证据** |
| `交接文件_GPT6_2026-09-17.md` | 历史交接文档（v2 视角，开头有 v3 指针） |

## 一条命令跑完

```powershell
cd "C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3"
.\rebuild.ps1            # 重建资产 + 45 项 Blender 侧检查（32 几何 + 13 史实）
```

要不要同步到 Unity 工程（`D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval`）：

```powershell
cd "...\queen_mary_v3\unity"
.\sync_to_unity.ps1 -ProjectPath "D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval"
```

Unity 侧四道门（都能用 `-batchmode -executeMethod` 跑，不用开界面）：

| 菜单 | 批处理入口 | 验什么 |
|---|---|---|
| Set up URP | `Naval.EditorTools.UrpSetup.SetUpBatch` | 建 URP 管线资产、按契约建材质、重导模型 |
| Build runtime ship | `Naval.EditorTools.ShipRuntimeBuilder.BuildBatch` | 仅碰撞件关渲染、舱室挂数据与碰撞体、生成 LOD 链、存预制体与 ShipDefinition |
| Validate ship asset | `Naval.EditorTools.ShipAssetValidator.ValidateBatch` | 契约 101 名、轴向、右舷、URP 材质、炮塔枢轴 |
| Render URP check images | `Naval.EditorTools.ShipPreviewRender.RenderBatch` | 逐像素查品红/黑屏，出五张校验图（优先渲预制体） |

当前状态：**四道门全绿**（`ship_runtime_build.json`、`unity_verification_urp.json`、`unity_render_check.json`）。

### 运行时船体做了什么

85 个网格里有 **24 个在船壳内部、永远看不见**（8 件装甲 + 13 个舱室 + 3 件水下件）——构建时
**关掉它们的 MeshRenderer**、加上 **trigger 盒碰撞体**，并把 `buoyancy_compartments.json` 的
体积/渗透率/可进水体积挂到舱室对象上（`ShipCompartment`）。结果：每艘船 draw call 从 85 降到 61，
同时"这一炮打中哪个舱、进不进水"有了世界里的答案。产物是
`Assets/Prefabs/Ships/HMS_Queen_Mary_1913.prefab` + `ShipDefinition` 资产。

> 碰撞体一律用**盒体 + trigger**，不用网格碰撞体：15 艘船 × 24 个网格碰撞体会压垮物理；
> trigger 则避免船与船互相卡住。射线检测记得传 `QueryTriggerInteraction.Collide`。

### LOD 链做了什么

静态本体生成四档 LOD（三份合并网格资产存在 `Assets/Meshes/Ships/`，挂进 `LODGroup`）：

| 档 | 屏幕高度 | 内容 | 渲染器 | 三角形 |
|---|---|---|---|---|
| LOD0 | > 0.20 | 原样全细节 | 61（45 静态 + 16 炮塔链） | 29,264 |
| LOD1 | > 0.08 | 静态本体按**材质**合并 | 17（1 合并 + 16 炮塔链） | 29,264 |
| LOD2 | > 0.03 | 再丢小件（索具 / 网 / 甲板小配件 / 炮廓凹口…） | 17 | 16,344（−44%） |
| LOD3 | > 0.01 | 扁平剪影，**本档关掉炮塔链** | 1 | 4,990（−83%） |

两条硬约束：

1. **炮塔链（16 个渲染器）在 LOD0/1/2 里始终保留**——它们要转，一旦被合进静态网格就永远转不了。
   所以 LOD1/2 的渲染器下限就是 17。
2. **按材质合并，不是按对象**：合并后子网格数 = 材质数（6），于是"1 渲染器 + 6 子网格 ≈ 6 次
   draw call"；按对象合会让子网格数等于对象数，等于白做。

> **一个踩过的坑（已修，并已加断言）**：炮塔渲染器原先**没有列进任何 LOD 档**。LODGroup 只开关
> "列在档里"的渲染器，所以它们在任何距离都会画；而 LOD3 的剪影里又含一份炮塔几何 ——
> 远档就成了"剪影里的冻结炮塔 + 真实炮塔仍在画" = 重复绘制 + 共面 z-fighting，而且**不报任何错**。
> 现在炮塔渲染器列进 LOD0/1/2 档、只在 LOD3 缺席；并加了一条断言：
> **凡是被合进 LOD 网格的渲染器，必须至少出现在一个 LOD 档里**，否则构建直接失败。

**屏幕高度阈值 0.20 / 0.08 / 0.03 / 0.01 是默认值，要对着真实相机调**——这批数字决定了切换距离。

### 已知的验证缺口（别当成"四档都验过了"）

渲染校验的五个视角都在**近距离**，因此 **LOD2 / LOD3 这两档没有被像素校验覆盖**，
报告也不记录"本次生效的是哪一档"。要补有两条路：加一个远距视角，或在报告里报出各视角
实际生效的 LOD 档。在那之前，LOD 链的结构性正确（档位、三角形数、渲染器归属）有断言保证，
**但"远看像不像那艘船"还没有像素证据**。

## 改动约定（谁改了什么）

1. **改资产 → 必须重建并跑验证**，把 `geometry_sha256` 的变化写进提交信息或交接记录，
   不要以"我记得改过"结案。
2. **不要手填绝对坐标**，贴体附件一律从 `halfbeam_at(y, z)` 派生。
3. **契约是唯一字段来源**：Unity 侧不要从 `object_manifest.json` 手抄字段；
   FBX 文件名也从契约读（`file_refs.fbx`），别硬编码。
4. **断言要写物理不变量，不要写实现细节**——曾经把"炮管局部位置必须为 0"写成断言，
   换代时立刻误报（正确写法是"原点落在耳轴上"）。
5. 不要把灰盒设定写成史实断言：新加的历史结论要么有 `source`，要么标 `user_spec_only`。
6. **C# 静态预检要对 Unity 工程跑，不要对 `queen_mary_v3/unity/` 跑**：

   ```bash
   cd D:/Unity/Projects/ThinkingFactory
   python tools/cs_precheck.py "D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval"
   ```

   它按 `<根>/Assets/**/*.cs` 找文件；融合后的 `unity/` 是 `Editor/` + `Scripts/` 结构，
   直接指过去会**扫到 0 个文件然后报"全部通过"**——那是假绿，不是真的过了。
   （同理，预检通过 ≠ 能编译，改完必须真的让 Unity 编一次。）
