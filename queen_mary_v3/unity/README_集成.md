# 玛丽王后号 → Unity 接线包

这个目录里的东西是**准备贴进 Unity 工程**的，不是资产本体。
资产本体在**上一级目录**（`..\`），两边靠 `sync_to_unity.ps1` 同步。

---

## 一、你要做的三步

### 1. 建工程（Unity Hub）

- New project → 模板选 **3D (URP)**（推荐：后面要做水面、泡沫、炮口焰，URP 在这台机器上已
  有 14.0.11 的使用经验）
- 名字建议 `QueenMaryNaval`，位置 `D:\Unity\Projects`
- 编辑器版本必须选 **2022.3.62f3c1**（本机已装的那个；旧验证记录也是这个版本）
- 若 URP 模板未安装，用 **3D (Built-in)** 也能跑：这三个 C# 文件与渲染管线无关，
  只是材质会走 Standard 而不是 URP/Lit。

### 2. 同步

```powershell
cd "C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3\unity"
.\sync_to_unity.ps1 -ProjectPath "D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval"
```

> **注意 Hub 会多套一层目录**：位置选 `D:\Unity\Projects` + 名字 `QueenMaryNaval`
> ⇒ 真正的工程根是 `D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval`
> （判断依据：根目录下同时有 `Assets/` 和 `ProjectSettings/ProjectVersion.txt`）。

**若脚本执行策略被拦，用下面这组等价命令**（在 Git Bash 里跑即可）：

```bash
SRC="C:/Users/杨睿/Desktop/HMS_Queen_Mary_建模成果_2026-09-17"
P="D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval"
mkdir -p "$P/Assets/Scripts/Naval" "$P/Assets/Editor" "$P/Assets/Resources/Ships/HMS_Queen_Mary_1913"
cp -f "$SRC/queen_mary_v3/unity/Scripts/Naval/ShipContract.cs" "$P/Assets/Scripts/Naval/"
cp -f "$SRC/queen_mary_v3/unity/Editor/ShipModelImportSettings.cs" "$P/Assets/Editor/"
cp -f "$SRC/queen_mary_v3/unity/Editor/ShipAssetValidator.cs" "$P/Assets/Editor/"
cp -f "$SRC/queen_mary_v3/HMS_Queen_Mary_1913_Refined_v3.fbx" "$P/Assets/Resources/Ships/HMS_Queen_Mary_1913/"
for f in ship_contract.unity.json object_manifest.json damage_model.json hydrostatics.json \
         buoyancy_compartments.json firing_arcs.json ship_contract.json; do
  cp -f "$SRC/queen_mary_v3/$f" "$P/Assets/Resources/Ships/HMS_Queen_Mary_1913/"
done
```

同步三件事：

| 来源 | 目标 | 内容 |
|---|---|---|
| `Assets/Scripts/Naval/ShipContract.cs` | `Assets/Scripts/Naval/` | 运行时契约类（JsonUtility 直接可读） |
| `Assets/Editor/ShipModelImportSettings.cs` | `Assets/Editor/` | 导入设置钉死（AssetPostprocessor） |
| `Assets/Editor/ShipAssetValidator.cs` | `Assets/Editor/` | 契约×模型校验 + 轴向实测 + URP 材质兜底 |
| `Assets/Editor/UrpSetup.cs` | `Assets/Editor/` | URP 管线资产 + 按契约建材质（见第六节） |
| `Assets/Editor/ShipMaterialRemap.cs` | `Assets/Editor/` | 把 FBX 材质槽按名重映射到 URP 材质 |
| `Assets/Editor/AxisProbe.cs` | `Assets/Editor/` | 轴映射探针读取端（见第五节） |
| `Assets/Editor/ShipPreviewRender.cs` | `Assets/Editor/` | URP 渲染校验图 + 像素检查（见第七节） |
| 上一级目录的 `*.fbx` `*.json` | `Assets/Resources/Ships/HMS_Queen_Mary_1913/` | FBX ＋ 全部数据文件 |

### 3. 验证

回 Unity，**先在 Console 确认没有编译错误**（见下面那条纪律），然后：

> 菜单 **Tools → Naval → Validate ship asset**

通过时屏幕会给你对象数、mesh 数、主尺度和偏航/俯仰的局部轴与符号；
详细报告同时写回 `..\unity_verification_urp.json`（不覆盖 v3 那份 `unity_verification.json`）。

---

## 二、这套代码在防什么

### 1. 防「手点导入设置漏一条」

`ShipModelImportSettings.cs` 把设置钉死，逐条理由写在文件注释里。三条最要紧：

- `isReadable = true` —— 运行时要在 mesh 上做查询（碰撞代理、射界 BVH、命中点）。不开就抛异常。
- `weldVertices = false` —— 硬边是靠不共享顶点做出来的，焊接会把硬边焊平；**而 Blender 端验证
  发现不了这个变化**。
- `optimizeMesh* = false` + `meshCompression = Off` —— 顶点顺序与顶点数据必须可预测，
  否则对象计数和 sha256 基线都失去意义。

### 2. 防「把灰盒设定当成史实」

契约里 `historically_certified: false`、`offsets_source: builtin_estimate` 是**故意留着的**。
验证只断言几何与层级，不断言"这艘船史实正确"。史实断言在 Blender 侧是单独一层（可开关、带 source）。

### 3. 防「轴向约定被静默改掉」

这是最容易出事的一项。校验器**不读设置、只测结果**：

- 舰艏方向 = `Barbette_A`（前）− `Barbette_X`（后）的世界坐标差，必须 ≈ **+Z**
- 向上方向 = `Rangefinder_CT`（司令塔顶）− `Steering_Gear`（水下）的差，必须 ≈ **+Y**
- 水线基准：`Steering_Gear` 必须在 **y < 0**（主甲板 y = +5.1，吃水 9.9 ⇒ 设计水线即 y = 0）
- 根节点缩放必须是 1（米就是米）

### 4. 防「游戏代码猜错了转塔正负号」

`ProbeAxis()` 对偏航/俯仰节点**逐个试自己局部的 ±X / ±Y / ±Z**，看哪个轴真的在转炮口，
再记录「正方向 = 向右舷 / 向上」对应的符号。原因是 Blender 用 `axis_up='Y'` 导出时把轴向转换
**烘进了节点**，局部 +Y 未必是舰体竖直轴 —— 照抄直觉写 `Quaternion.Euler(0, yaw, 0)` 很可能转反。

报告里的三个字段就是游戏要用的写法：

```csharp
// yawAxisLocalInNode = "Y"、unityLocalYawSign = -1 时的含义：
turret.localRotation = restYaw * Quaternion.AngleAxis(-1f * yawCommandDeg, Vector3.up);
pivot.localRotation  = restPitch * Quaternion.AngleAxis(-1f * elevationCommandDeg, Vector3.right);
```

> **第一次跑完请把这些值填回 `ShipAssetValidator.cs` 顶部的 `BaselineYawSign` / `BaselinePitchSign`。**
> 填之前它们是"只报告"（0），填之后才变成阻塞断言 —— 以后谁改了导出轴向都会立刻红。

---

## 三、纪律（从《会思考的工厂》那边学来的，同样适用）

1. **Unity 编译失败时会留着上一份程序集继续跑** —— 症状是"新代码不生效"而不是报错。
   所以"菜单出现了""能点"都不代表编译过。改完 C# 先看 Console。
2. **完整编译错误在** `%LOCALAPPDATA%\Unity\Editor\Editor.log`（`grep "error CS"`），
   Console 常常只露一条并且被截断。
3. **错误是分层的**：有语法错误时编译器不做语义分析 ⇒「修一个露一个」是必然，每修一轮重读日志。
4. **不要清零导入模型内部的旋转**。偏航/俯仰枢轴的正负号就藏在那里，清零等于把炮塔转反。
5. 改 FBX 后不要 `git add -A` 全提：同一脚本两次导出的字节可能不同而几何没变，
   先比对象数/mesh 数（契约里就有），只提交真变的。

---

## 四、批处理（可选）

```powershell
& "D:\Unity\Editor\2022.3.62f3c1\Editor\Unity.exe" `
  -batchmode -quit -projectPath "D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval" `
  -executeMethod Naval.EditorTools.ShipAssetValidator.ValidateBatch `
  -logFile "C:\Users\杨睿\WorkBuddy\2026-09-17-17-33-38\_unity.log"
```

退出码 0 = 通过、1 = 失败，报告同样写回 `..\unity_verification_urp.json`。
**跑批处理前必须关掉编辑器**（同一个工程不能被两处打开，判据是 `Temp/UnityLockfile` 是否存在）；
批处理用 `-nographics` 不必加，缺图渲染反而更稳。

> ⚠️ **别在 2 分钟内连着起第二个 Unity 进程**。实测会遇到许可证 IPC 握手失败
> （`Failed to handshake to channel: "LicenseClient-..."` / `No ULF license found`），
> 这时批处理会**静默什么都不做就退出**：没有编译错误、没有 `[Naval]` 输出、报告也不生成。
> 判据就看日志里有没有 `[Naval]` 那一行——没有就是没跑成，不是"通过了"。

---

## 五、轴向约定（**实测过，别靠推理改**）

用 5 个不对称标记件做探针，让 Unity 直接报出它们的落点，得到的确切映射是：

```
Unity = (-x, z, -y)        即：
    Blender +X(右舷)  ->  Unity -X
    Blender +Y(舰艏)  ->  Unity -Z
    Blender +Z(向上)  ->  Unity +Y
```

这是一次**反射**（det = −1），所以船本身没有镜像问题；但它等价于"整船绕竖轴转了 180°"：
`transform.forward` 会指向舰艉，每座炮塔的静置偏航都差 180°。

**修法已落地在资产侧**：`queen_mary.py` 的 `export_fbx()` 在导出时把根节点绕竖直轴转
`EXPORT_YAW_DEG = 180°`（转完再复原，所以 `geometry_sha256` 不变）。因此出货的 FBX 里
舰艏指向 −Y，到 Unity 就落在 **+Z** ✓，同时右舷落在 +X ✓，`forward` 与 `right` 同时正确。

> **改这个偏转角必须同步 `verify_fbx.py`**：它拿 `object_manifest.json`（Blender 内部坐标，
> 舰艏 +Y）当期望值，所以要先把期望坐标施加同一个偏转再比对。两边读的是同一个常量。

**注意 `axis_forward` / `axis_up` 这两个导出开关在 Unity 侧没有效果**——实测把
`axis_forward` 从 `'-Z'` 改成 `'Z'`，FBX 哈希变了而 Unity 里的朝向一字不差
（Unity 的导入器忽略文件头声明的 front 轴）。**朝向只能在几何上拧。**

任何时候想复核，或换一艘新船时，重跑探针即可：

```bash
# 1) Blender 侧生成探针（塞入不对称标记件后按资产同款参数导出）
blender --background --python queen_mary/probe_axis_convention.py -- --out "<工程>/Assets/_AxisProbe"
# 2) Unity 侧读出落点（菜单 Tools > Naval > Probe axis convention）
```
`_axis_probe_unity.txt` 会同时给出 Unity 实测坐标与 Blender 参考坐标，一眼就能对上。

---

## 六、URP（已切换）

工程模板本来是 **Built-in 3D Core**，已切到 **URP 14.0.12**（与同版本 Unity 的另一个工程一致）。
包从国内源 `packages.unity.cn` 解析 —— 不需要梯子。

跑一次装配就完事：

> 菜单 **Tools → Naval → Set up URP**　或　批处理 `Naval.EditorTools.UrpSetup.SetUpBatch`

它按依赖顺序做三件事：

1. 建 `Assets/Settings/QueenMary_UniversalRenderer.asset` 与 `QueenMary_URP.asset`，
   并设为 `GraphicsSettings.defaultRenderPipeline`。
   —— 只设默认管线即可：各质量档的 `renderPipeline` 为 null 时会继承它。
2. 按**契约里的 `materials` 表**建 `Assets/Materials/Naval/<名字>.mat`（URP/Lit）。
   **灰度值不在 C# 里重复一份** —— Blender 的 `MATERIAL_SPECS` 是唯一来源，
   契约把它交给 Unity。色值是**线性**的：Blender 的 Base Color 与 URP 的 `_BaseColor` 都是线性，
   直接搬运、不做 sRGB 转换。
3. 重导舰船 FBX，让 `ShipMaterialRemap` 把材质贴上去。

### 为什么需要第 3 步

Blender 导出的 FBX 里材质是**内嵌**的、走 Built-in 的 Standard shader。在 URP 下这会让
**整艘船渲染成品红**，而且这个故障是**静默**的：船在、三角形也在、几何与坐标全对，
只是颜色全错 —— 不看画面发现不了，其它验证也一条都不会响。

- `ShipMaterialRemap.cs`（AssetPostprocessor）按**名字**把材质槽指到 `Assets/Materials/Naval/`。
  材质资产必须先存在，回调才认得出来 —— 所以装配脚本建完材质会重导模型。
- 找不到对应材质时它**打警告并列出缺失的名字**：宁可吵，也不要静默出品红。
- 验证器另有一条兜底：**每个材质槽的 shader 名字必须以 `Universal Render Pipeline/` 开头**，
  否则阻塞失败。这样"改成品红"永远不会以绿的方式溜过去。

## 七、渲染校验图（像素级自证）

> 菜单 **Tools → Naval → Render URP check images**　或批处理 `Naval.EditorTools.ShipPreviewRender.RenderBatch`

它开一个临时相机和灯，把船渲五个视角，**逐像素检查**，图片与报告写回资产目录：

```
unity_preview/{Overview,Starboard,Top,Bow,Stern_Aft}.png
unity_render_check.json
```

### 判据（都是阻塞级）

| 检查 | 阈值 | 抓什么 |
|---|---|---|
| 品红像素占比 | < 2% | 材质 shader 不对 → 整船品红。判据是「红蓝都高且明显高于绿」——**灰色船体 r≈g≈b，永不误报** |
| 舰船像素占比 | > 1% | 管线配错 → 全黑或只剩背景 |
| 包围盒完整入画 | 必须 | 相机太近把船切了（自动取景会先往后拉 8 次） |

### 为什么值得让它渲

这两类故障**都是静默的**：船在、三角形也在、几何/层级/坐标全对，只有颜色和画面不对。
对象数、契约校验、轴向断言一条都不会响。它们只在像素上现形。

### 报告里还有两件"事实"（只报告、不断言）

- **`bowOnScreen`**：舰艏在画面哪一侧。用 Barbette_A / Barbette_X 投影到视口比大小得出。
  正对舰艏/舰艉的视角两个炮座重合，这时给 `head-on` 而不是硬编一个 left/right。
  —— 这条存在的意义是**防止被自己的眼睛骗**：第一版侧视图偏暗，我把艉部的钝端看成了舰艏，
  是俯视图（艏尖艉宽，形状本身就是判据）和这条数值报告一起纠正了我。
- **`greyLevels`**：画面里出现的量化灰度级数（实测 13–20 级）。一片平灰说明材质没生效，
  多个级数才说明确实按部位用了不同材质。

### 两个踩过的实现坑

1. **别在批处理里新建场景**：当前是"未保存的未命名场景"时，Unity 拒绝再开附加场景
   （`Cannot create a new scene additively with an untitled scene unsaved`）。
   改成把临时物件放进当前场景、**渲完在 finally 里销毁**，渲染设置的改动也一并还原 ——
   这样从菜单跑时不会把你正开着的场景换掉。
2. **正交相机的自动取景要放 `orthographicSize`，不是距离**：正交下距离不影响构图，
   拉 8 次也没用（Top 视图就是这么挂的）。另外正俯视的 `LookAt` 上方向不能取 +Y（与视线平行
   会退化），取 -X 才能让船长横放在画面里、且舰艏落在右侧。

## 八、还没做的

- `ShipDefinition` ScriptableObject（把契约资产化，供 Inspector 引用）
- 损伤模块的碰撞代理生成、LOD 链（LOD0–3）、命中区域与 `damage_model.json` 的装配
- 装甲与内部模块走"仅碰撞、不渲染"层（它们在契约里已单独成组，不用渲染网格）
