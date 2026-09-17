# HMS Queen Mary — 灰盒标杆舰 v2

本资产用于一战海战游戏：验证舰体比例、关键布局、炮塔枢轴、稳定命名和 Unity 导入。
它是按用户确认方案制作的灰盒，不是经过舰体线型、装甲或 1913 年装备考证的精确复原。

v2 相对 v1（v1 原稿见 `_v1_backup/`）的实质变化：

| | v1 | v2 |
|---|---|---|
| 舰体几何 | 全船共用一个缩放截面，艏艉收成刀锋 | 22 站位型值表驱动，巡洋舰式尾，圆舭 |
| 附件定位 | 手填绝对坐标 | 全部从船体表面派生（`halfbeam_at`） |
| 甲板 | 单层平板 | 艏楼/艉楼各自成模块，带舷弧 |
| 内部模块 | 8 个空对象（无体积） | 14 个体量 + 10 件装甲，带出处 |
| 验证 | 29 项，几何与史实混在一起 | 20 项几何不变量 + 12 项史实假设，分层 |
| 对象数 | 169（150 mesh） | 98（82 mesh），装饰件已合并 |
| 射界 | 无 | 由几何扫描算出，写入 `firing_arcs.json` |

## 打开和重建

- `HMS_Queen_Mary_1913_Greybox.blend`：Blender 源场景，内嵌完整 `queen_mary.py` 文本。
- `HMS_Queen_Mary_1913_Greybox.fbx`：供 Unity 导入，98 个语义对象，82 个网格，9,660 三角面；不含预览相机。
- `queen_mary.py`：自包含生成脚本，仅使用 Blender 自带的 bpy、bmesh、mathutils 和 Python 标准库。
- `rebuild.ps1`：重建并验收。几何不变量失败即中止；史实假设失败只报警告。
- 预览图：`Overview.png`、`Starboard.png`、`Top.png`、`Bow.png`、`Stern_Detail.png`、`Stern_Aft.png`。侧视、俯视的船头在右侧。
- `object_manifest.json`、`objects.csv`、`created_objects.txt`：对象角色、父子关系、原点、尺寸和世界包围盒。
- `damage_model.json`、`hydrostatics.json`、`buoyancy_compartments.json`、`ship_contract.json`：
  游戏侧直接消费的数据（命中区域与系统图、静水力、进水体积、扁平化契约）。见"战斗数据层"。
- `_diagnose_hidden.py`：诊断小工具，检查内部模块是否真的被船壳遮住（需要时再跑）。

在本文件夹打开 PowerShell：

```powershell
.\rebuild.ps1
```

也可以用 `-BlenderExe '完整路径/blender.exe'` 指定另一套 Blender。`-SkipRender` 只更新模型与清单。
实际执行版本为 **4.5.14 LTS**；脚本使用 Blender 3.x/4.x 共用 API，但没有在每个 3.x/4.x 版本分别运行。
生成过程中出错会写入 `build_result.json` 的 traceback。不要把旧 FBX 的存在视为本次构建成功。

## 舰体数据：型值表驱动

`OFFSETS` 是整船的单一数据源：每站一行 `(y, 甲板半宽, 水线半宽, 龙骨 z, 平板龙骨半宽)`，单位米。
船体网格、甲板、炮廓开口、防雷网、舰尾步廊、装甲板、内部舱室全部由它推导：

- `halfbeam_at(y, z)`：任意站位、任意高度处的半宽——附件的唯一吸附依据。
- `deck_halfbeam(y)`：甲板边线。`forecastle_z(y)` / `quarterdeck_z(y)`：带舷弧的甲板高度。
- `keel_at(y)`：龙骨线。

**换真实型线不需要改代码**：在本目录放一个 `hull_offsets.json` 即可覆盖：

```json
{"sources": "RMG 图纸编号 / 页码", "stations": [[y, 甲板半宽, 水线半宽, 龙骨z, 平板半宽], ...]}
```

`object_manifest.json` 的 `offsets_source` 会记录当前用的是内置估算还是外部文件。
主尺度是规定值且精确：213.4 × 27.2 × 15.0 m，龙骨 −9.9 m，主甲板 +5.1 m。

## 模块合同（战斗系统用）

**保持独立、可逐个寻址的对象**（不要合并）：

- 船体与甲板：`Hull`、`Forecastle`、`Quarterdeck`
- 上层建筑：`Superstructure` 组下的 `Bridge`、`Bridge_Upper`、`Bridge_Wings`、`Bridge_Visor`、`Conning_Tower`、`B_Superfiring_Deckhouse`、`Aft_Deckhouse`、`Aft_Platform`
- 炮塔链（16 个可动模块）：`Turret_A/B/Q/X`（水平枢轴）→ `Elevation_*`（俯仰枢轴，前部耳轴）→ `Barrel_*_Port/Starboard`（原点即各自耳轴，炮口在局部 +Y 12.4 m）
- `Barbette_A/B/Q/X`（固定炮座，含装甲属性）
- `Funnel_1/2/3` 与 `Funnel_*_Uptake`、`Mast_Fore`、`Mast_Main`
- 副炮 16 门：`Casemate_Port_1..8`、`Casemate_Starboard_1..8`（原点在炮廓口，局部 +Y 指向舷外，可各自转向）
- `Sternwalk`、`Torpedo_Net_*_Stowed`
- 装甲：`Armour_Belt_229mm`、`Armour_Upper_Belt_152mm`、`Armour_Belt_Taper_*`、`Armour_Deck_64mm`、`Armour_Deck_25mm`、`Armour_Bulkhead_Fwd/Aft`
- 损伤体量：`Magazine_A/B/Q/X`、`Boiler_Room_1..7`、`Engine_Room_1/2`、`Steering_Gear`
- `Rudder`、`Propeller_Shafts`、`Rangefinder_CT`、`FX_Anchors`

**只合并装饰件**（纯外观，无战斗语义）：`Casemate_Openings_Port/Starboard`、`Sternwalk_Rails`、
`Torpedo_Net_Port_Mesh/Starboard_Mesh`。

对象预算：可渲染网格 ≤ 65，总对象 ≤ 110（验证会拦截）。装甲与内部体量在 Unity 里应放到
**仅碰撞层**（关掉 MeshRenderer 或用碰撞代理），它们不该占 draw call。炮口特效挂点用
`FX_Funnel_*_Smoke`、`FX_Mast_*_Top`，不必再从网格里推。

Blender 中炮塔绕自身局部 Z 轴旋转；`Elevation_*` 绕局部 +X 轴正转可抬炮。A/B 初始水平旋转 0°，Q/X 为 180°。
俯仰原点在炮塔局部 `(0, 4.0, 1.5)` m。

## 布局（由甲板函数推导，不是手填）

| 对象 | 中心 Y（m） | 基座 Z（m） | 说明 |
|---|---:|---:|---|
| Turret_A | +60 | 8.31 | 艏楼甲板 7.31 + 1.0 |
| Turret_B | +46 | 12.00 | 背负式，高 A 3.69 m |
| Bridge / Mast_Fore | +32 | 7.19 / 16.19 | 前桅立在舰桥顶 |
| Funnel_1 | +23 | 9.59 | 椭圆：4.9 × 7.6 m |
| Funnel_2 | +7 | 9.50 | 圆形：直径 7.0 m |
| Turret_Q | −6 | 7.97 | 中置，静置朝艉（史实射界受限的那座） |
| Funnel_3 | −27 | 7.64 | 椭圆：4.9 × 7.6 m |
| Mast_Main | −38 | 9.30 | 立在艉甲板室顶 |
| Turret_X | −68 | 6.68 | 艉楼甲板 5.48 + 1.2 |
| Sternwalk | −98 … −106.5 | 3.06 | 环绕舰艉的 U 形平台，舷外 1.3 m |

三座烟囱顶端统一在 +22.0 m（与史料改装一致）。艏楼甲板由 6.85 m 升到艏部 7.50 m，
艉楼甲板由 5.10 m 升到艉部 5.72 m——都是估算舷弧，等总布置图。

## 由几何算出的射界

`firing_arcs.json` 是验证时顺手产出的游戏数据：以炮管中心线为样本、对障碍物包围盒做净空测试
（要求 0.30 m），5° 一档扫描 0–355°、仰角 0/5/10/15/20°，输出每座炮塔在各仰角下的可射角度区间。
角度以**该炮塔静置朝向**为零位（A/B 朝艏，Q/X 朝艉）。

当前结果定性上和历史吻合：A/B 无法向艉射击（被上层建筑挡住），Q 无法向前射击（被舰桥与前部结构挡住），
X 在高仰角下接近全向。它是保守近似，不是弹道或爆风模型，也不是手工填的射界表——换型线或移动部件后会重新算。

## 战斗数据层

四个由脚本生成、游戏侧直接吃的数据文件（不要手改）：

| 文件 | 内容 |
|---|---|
| `damage_model.json` | 17 个语义命中区域（弹药库／机舱／侧装甲／炮座／炮塔本体／指挥所…）、每舱的侧/甲板/舱壁防护厚度、**系统图**（弹药库→炮塔供弹、锅炉舱→主机→轴、烟囱排烟源、舵机→舵、火控→四塔），每条链接带 `published` / `estimate` 状态 |
| `hydrostatics.json` | 由型值表积分的静水力：排水体积、水线面面积、浮心 LCB/VCB，并与公开满载排水量对比 |
| `buoyancy_compartments.json` | 每个可进水舱室的体积、形心、水线以下体积、渗透率与可进水体积，以及占排水体积的比例 |
| `ship_contract.json` | 扁平化契约（Unity `JsonUtility` 友好）：主尺度、模块名按角色分组、四座炮塔的枢轴/耳轴/炮口/初始偏航/仰角限值、副炮列表、文件索引 |

**静水力是对型线估算的独立校验**：浸水体积 30,663.7 m³ → 31,430 t，对公开满载 32,160 t 只差
**−2.27%**；LCB +1.58 m、VCB −3.89 m、水线面 3,073.6 m² 均在合理区间。也就是说，虽然 `OFFSETS`
仍是估算值，但它的**体积特性已经被一个公开数字约束住**了——如果之后有人改动型值，这条检查会立刻报警。

可进水体积合计 7,176 m³（占浸水体积 23.4%），可作为进水/沉没模型的起点（尚未做水密分割与稳性计算）。

系统图也写在对象上：每个模块带 `system_links`（如 `feeds_feed_hoist_of:Turret_A:published`）、
`hit_zone` 与 `exposure`（internal / external）属性。

## 数据与出处

每一条非显然的数字都带 `source` 字段，指向 `SOURCES` 里的条目；`estimate` 表示这是灰盒估算，
不可当成史实引用。要点：

- 1913 服役原状：无高射炮（1914 年 10 月才加装）、防雷网在位、射控指挥仪仰角上限 15°21′（棱镜 1916 年才装）。
- 主炮：4 × 双联 343 mm（13.5″/45 Mk V），每炮 110 发、全舰 880 发，1,400 lb 弹、760 m/s、20° 时 21,708 m。
- 副炮：16 × 102 mm（4″/50 Mk VII），单层甲板每舷 8 门；射速 6–8 发/分、每炮 150 发。
- 动力：42 台 Yarrow 锅炉分 7 个锅炉舱、2 个主机舱、4 轴；设计 75,000 shp、试航 83,350 shp、28 节。
- 装甲：主带 9″（229 mm）KC、上带 6″、舱壁 4″、炮座 9″/8″、炮塔面 9″/顶 64–83 mm、司令塔 10″、烟道 38 mm。
- 火控：Pollen Argo Clock Mk IV；司令塔顶 9 英尺测距仪（2.74 m 基线）已建模为 `Rangefinder_CT`。
- 舰尾步廊：本舰是英国第一艘装舰尾步廊的战列巡洋舰，属识别特征。

内部舱室（锅炉舱、弹药库、机舱）的**位置与尺寸都是估算**，只保证落在船体壳内（脚本会自动夹紧并记录
`clamped_to_hull`）。装甲厚度是公开数据，装甲覆盖范围是估算。

## 验证分两层

`verify_blender.py` 把检查分成两层，`rebuild.ps1` 据此决定是否中断：

- **geometry（20 项，阻塞）**：语义名齐全、主尺度与包络、单位与原点、模块顺序、附件不得超出船体
  （逐顶点对 `halfbeam_at` 判定，含各角色的舷外允差）、结构不得悬空、甲板模块必须落在甲板函数上、
  内部体量必须在船体壳内、炮塔枢轴链与运动、静置炮管净空、副炮每舷 8 门且原点在船体表面、
  装饰件已合并而战斗模块保持独立、对象预算。
- **assumption（12 项，非阻塞）**：所有史实断言都带 `source` 与 `status`
  （`matches_source` / `user_spec_only` / `conflicts_with_source`）。它们**不会**因为"通过"而变成考证结论。

这两层是 v1 的教训：v1 的 29 项检查把灰盒设定（每舷 8 门、两座三脚桅、F1/F2 更近）写成断言，
方案本身错也照样全绿——副炮层高与桅杆形制就是这样溜过去的。

配套：`verify_fbx.py` 检查 FBX 往返后语义模块、层级、世界包围盒（误差 < 0.1 mm）、枢轴链和装饰合并状态；
`firing_arcs.json`、`build_result.json`（含同进程二次生成比对）是最终的证据文件。

## Unity 2022.3 导入约定

在独立临时工程中实际导入过（v1 的 FBX）。采用：

- Scale Factor = 1，Use File Scale = true。
- Bake Axis Conversion = true，Preserve Hierarchy = true。
- 不导入相机、灯光；资产类型使用普通模型，不启用 Humanoid。
- URP 中为材质槽指定简单的 `Universal Render Pipeline/Lit` 灰色材质；Blender 节点材质不能视为已验证的 URP Shader。

导入后船体世界尺寸应约为 **X 27.2 × Y 15.0 × Z 213.4 m**，船头朝 Unity +Z，龙骨 Y≈−9.9，主甲板 Y≈+5.1。
FBX 保留转换后的根变换和子对象局部坐标，**不要随意清零导入模型内部的旋转**。可在外层新增一个
位置／旋转为零、缩放为一的游戏控制根对象。炮塔局部轴与 Unity 世界轴不同，导入时记录初始局部旋转后叠加命令：

```csharp
Quaternion restYaw = turret.localRotation;
Quaternion restPitch = elevation.localRotation;
turret.localRotation = restYaw * Quaternion.AngleAxis(-yawDeg, Vector3.forward);
elevation.localRotation = restPitch * Quaternion.AngleAxis(-elevationDeg, Vector3.right);
```

Q/X 的 `yawDeg` 是相对各自朝艉的初始方向。改变导入设置或烘焙方式后要重新验证轴向和符号。

> **注意**：`unity_verification.json` 记录的是 **v1 的 FBX**（其 `sourceFbxSha256` 与当前 FBX 不一致）。
> v2 的对象数、层级和尺度已经变了，必须在 Unity 里重跑一次导入验证，不要直接引用这份旧记录。

## 仍不确定、需要素材才能收口的部分

1. **副炮层高**：史料说 16 门 4 英寸炮"大部分装在艏楼甲板的炮廓内"，但这句话有两种读法
   （炮位在艏楼甲板之上，还是艏楼之下的主甲板层）。脚本里是开关 `CASEMATE_PLACEMENT`：
   默认 `between_decks`（炮位在主甲板上、艏楼甲板之下，与 v1 一致），另一档 `on_forecastle`
   会把炮位抬到艏楼甲板并自动补一段舷墙。**需要带日期的照片或图纸定案。**
2. **两座三脚桅**：`worldwar1.co.uk` 记本舰原为单桅杆桅、后改三脚桅。目前仍是两座三脚桅（用户要求），
   验证里标成 `user_spec_only`。需要照片。
3. **舰体型线**：`OFFSETS` 是估算值。给出横剖型线图后直接替换 `hull_offsets.json`，其余全部自动跟随。
4. **总布置图**：炮塔/烟囱/桅杆的纵向站位、艏楼艉楼分界（现为 Y=−18）都是估算。
5. **副炮炮廓内部、网具、桅顶细节**：仍是简化表达。
6. **LOD 与 draw call**：本资产只做了模块拆分与装饰合并，还没有 LOD 链；同屏 10–30 艘的最终预算
   要靠 LOD 解决，而不是靠破坏模块。

参考素材：第一张线图用于主要布置；第三张彩图明确标注 05/1916，只借用共同轮廓与布局；
第二张照片没有经过舰名及日期核实，只作一般炮塔／舰桥层次参考。
馆藏入口：[Royal Museums Greenwich — Queen Mary 馆藏索引](https://www.rmg.co.uk/collections/object?vessels%5B%5D=Queen+Mary+%281912%29)、
[馆藏模型](https://www.rmg.co.uk/collections/objects/rmgc-object-67366)。
