# Queen Mary v3 灰盒可见层精修与 Unity LOD 阈值补全

> Generated 2026-09-18 · depth: standard · sources: 4 findings files (F1–F4, ~55 claims) · workspace: research/queen-mary-refine-lod/

## Executive summary

- 1913 原状的中距识别点不是贴图细节，而是：**单层副炮甲板带、中烟囱更圆、舰尾步廊、pole mast、无 AA、在位防雷网、四座轴线双联装主炮** [1][2][3][4][6][12]。Tiger（1914）是常见错误参照，副炮是 6 英寸而非 4 英寸 [8]。
- 50–200 m 对 213.4 m 舰体仍几乎是「贴脸」：船长与 60° 水平视场同量级，该距离**必须保留剪影质量块**（船体长宽比、烟囱、主炮塔布局、上层建筑块、桅杆型式）；可先降级的是单门副炮、小艇、栏杆、索具、甲板小件 [14][2][3][4]。
- Unity LOD 切换是**屏幕高度百分比**，不是米；`QualitySettings.lodBias` 会把作者阈值整体「压低」（bias=2 时 0.20 实际约按 0.10 生效）[3][4][12]。阈值与 bias 必须解耦成可配置系统。
- `LODGroup.size` 是局部包围尺寸，**不是船长**；当前基准反解 ≈214 m 的写法把纵向长度当 size，会把阈值距离标定得过远 [7][1]。
- 灰盒多舰应使用**手工 LOD Group**（可丢 renderer/材质），不要用 Unity Mesh LOD 自动简化硬表面多片舰体 [9][10][4][5]。
- 自动档在现基准相机（~1.4–1.9 km、bias=2）下 15 艘全 LOD0 是公式结果，不是统计错误；要跨档需双相机剖面 + 可配置阈值，并在报告里记录 size/bias/fov/距离 [15]。
- 未取得海战大厂公开 LOD 米制表；数值建议均为**公式推导**，须在本工程真机相机下验收，不能当行业标准 [speculative on absolute numbers]。
- 史实与模型仍有源冲突（服役日、总长/水线长/排水量）；灰盒继续 `historically_certified:false`，精修点标注 source/estimate [11][10]。

## Background & scope

本研究服务仓库 `HMS_Queen_Mary_建模成果_2026-09-17` 的 compose-next 特性：**灰盒可见层精修**（`queen_mary.py`，50–200 m）+ **LOD 阈值双相机剖面配置**（Unity `ShipLodBuilder` / 契约 / 基准）。不做型线重构、不做完整损管/火控。假设：舰长规格已锁定 213.4 m、Unity 2022.3 URP、同屏约 15 艘、观察 50–200 m 与舰队远距并存。

## 史实识别特征（精修只动可见层）

| 特征 | 1913 口径 | 对灰盒的含义 | 出处 |
|---|---|---|---|
| 副炮 | 16×4″ 单装、每舷 8、**单层甲板** casemate | 保留一层副炮带的连续剪影，不必逐门写实 | [1][4][2] |
| 中烟囱 | 相对 Lion **更圆** | Funnel_2 轮廓/半径可略强化为识别点（estimate） | [2] |
| 舰尾步廊 | 近姊妹舰没有的 sternwalk；本舰为 RN 首舰之一 | 必须在侧视/斜视可见，不可当可丢小件 | [2][5] |
| 桅杆 | 建成 **pole mast**，后改 tripod | v3 已是单杆+拉索；1913 灰盒不要改成三脚 | [2][12] |
| 高炮 AA | **1914-10 才加装** | 1913 灰盒禁止出现 AA | [6][12] |
| 防雷网 | 战时拆除 | 1913 应保留 stowed nets | [12] |
| 主炮 | 4×2 轴线炮塔，前二后二；无第五座后部超射 | 保持 A/B/Q/X 可寻址；勿加第五塔 | [3][6] |
| 误参照 | Tiger：12×6″、烟囱/上层建筑重排 | 精修禁止抄 Tiger 布局 | [8] |

尺度源不一致（700 ft / 698 ft WL / 703 ft 6 in OA；排水量 26,770–31,650 区间不同表）[11][5]。**LOD 标定继续用工程已锁定的 213.4 m + 实测 `LODGroup.size`，不跟某一文献漂移。** 服役日期二级来源冲突（1912 / 1913-04-09 / 1913-08），不写认证服役日 [11]。

## 中距可读性层次（灰盒）

历史与识别证据一致：交战距离靠**天空剪影**（烟囱数量/形状、桅杆、炮塔块）辨识；烟囱/桅杆损坏后几乎无法辨认 [2][3][4]。

对 50–200 m：

1. **必须保留（LOD0/LOD1）**：船体 L/B 轮廓、三烟囱质量、四炮塔块与背负关系、舰桥/上层建筑块、单杆桅与基本拉索、舰尾步廊、副炮层带（可为合并带，不必 16 门独立）。
2. **可优先降级（LOD2+）**：单门副炮凹口细节、小艇、栏杆、细索具、甲板小件、装饰合并件。
3. **运行时仍独立**：炮塔链（yaw/pitch/barrels）在 LOD0/1/2 必须可动——这是仓库硬约束，不因「美化」合并进静态网格。

研究中出现一处需纠正的泛化：舰队识别类文献常用「多烟囱质量块」举例，**本舰是 3 座烟囱而非 4**；精修与 LOD 剪影均以契约 3 funnel 为准。

## Unity LOD 语义与阈值系统

- 层级切换输入：`LOD.screenRelativeTransitionHeight ∈ [0,1]` = 屏幕高度占比 [1]。
- 全局 `lodBias`：≥1 保持高细节更久；官方示例 bias=2 使 50% 事件发生在 25% [3][4]。本工程 Standalone 质量档 bias 常为 2 → 作者写 0.20/0.08/0.03/0.01 时**生效阈值约 0.10/0.04/0.015/0.005**。
- 距离换算（与 `ShipFleetBenchmark` 现用公式一致）：  
  `relH = LODGroup.size * lodBias / (2 * d * tan(fov/2))` [8]。
- `LODGroup.size` 为 local bounds 尺寸；应 **RecalculateBounds 后实测**，禁止把 213.4 m 舰长直接当 size [7]。
- URP 14 不提供 lodBias；只提供 LOD Cross Fade / dither 类型 [10]。
- 补充杠杆：`Camera.layerCullDistances`、`QualitySettings.maximumLODLevel`、小网格屏幕剔除（自定义 LOD 下应谨慎，必要时 0 或 Disallow）[12][9]。
- 标定工具：`ForceLOD(-1)` 恢复自动；验收要记 `lodBias / size / fov / d / 估计档位分布` [14]。

### 建议双剖面（推导值，非官方表）

前提：`size` 用**实测包围高度或构建写入的 LODGroup.size**（若构建错误地用了船长 ≈214，下列距离结论按 214 示意；实施时以真值重算）。`recommendedLodBias = 1`，阈值按「作者名义值」配置，避免和质量档 bias 叠乘后无法复现。

| 剖面 | 意图 | 建议 screenHeights（LOD0→3） | 预期（size=214, fov=50°, bias=1） |
|---|---|---|---|
| `tactical_50_200m` | 战术近距，剪影优先 | 0.45 / 0.18 / 0.06 / 0.02 | 50–200 m 的 relH ≈ 4.6–1.15 → **LOD0**；编队远端 ~400 m ≈0.57 → 仍偏 LOD0，若要跨 LOD1 可把 LOD0 阈值提到 ~0.60 |
| `fleet_1_2km` | 舰队远距，自动档必须可观测跨档 | 0.40 / 0.18 / 0.07 / 0.025 | 1.7 km relH≈0.135 → **LOD2**；2.3 km≈0.10 → LOD2；3 km≈0.077 → LOD2/3 边界 |

实施原则：阈值进 JSON/ScriptableObject，`ShipLodBuilder` 不再写死；验收报告记录剖面名与实测 relH；**引用结论时用档位顺序与三角形削减，不引用单次 ms**。

## 灰盒精修优先级（可见层，不重做型线）

| 优先级 | 动作 | 依据 | 数据标签 |
|---|---|---|---|
| P0 | 确认/强化：无 AA、pole mast、sternwalk 可见、3 烟囱、副炮单层带 | [2][4][5][6] | 与既有史料一致者可标 source |
| P1 | 中烟囱截面略圆/略异于前后（识别点） | [2] | estimate + source 引用 |
| P1 | 上层建筑块体在 50–200 m 更「块面清晰」（倒角/比例，不堆小件） | [2][3][4] | estimate |
| P2 | 索具/栏杆/小件服务中距可读即可，细节留给近景或远档丢弃 | [14] | estimate |
| P2 | LOD3 剪影继续合并烟囱+桅杆+炮塔块；**不**把炮塔链合进 LOD0/1/2 静态网格 | 仓库硬约束 + [9] | 流程约定 |
| 不做 | Tiger 布局、第五炮塔、1914+ AA、型线数字重写、贴图写实 | [3][6][8] + brief out-of-scope | — |

## Comparison

| 方案 | 战术 50–200 m | 舰队 ~1.7 km 自动档 | 配置面 | 风险 |
|---|---|---|---|---|
| 保持写死 0.20/0.08/0.03/0.01 + 质量档 bias=2 | 长期 LOD0（识别完整） | 仍可能全 LOD0（size 大时） | 无 | 无法复现、跨档不可演示 |
| 双剖面 JSON + bias=1 名义阈值 | LOD0 为主，符合识别需求 | 可设计为 LOD2 | `lod_profiles.json` + Definition | 需真机验收 relH |
| 仅降 bias 不改阈值 | 变化有限 | 可能提前降档 | 质量设置 | 与其它系统耦合，报告难复现 |

推荐：**双剖面可配置阈值 + 构建写入实测 size + 基准记 bias/profile**。

## Open questions

- 未拿到 Admiralty/Jane’s/Dreadnought Project 一级史料；中烟囱「更圆」等识别语句目前主要来自二级来源 [1][2]。
- 服役具体日期与排水量/总长的源间冲突未消解 [11]。
- 无 WoWS/SoT 等海军游戏公开 LOD 米制阈值表；绝对阈值仍是工程推导 [F4 dead ends]。
- 真机 `LODGroup.size`、游戏相机 FOV/编队纵深尚未锁定——实施验收时必须先测再锁。
- Cross Fade / GPU Resident Drawer / Small Mesh Culling 是否在 15 舰 URP 工程开启，本轮默认不动管线全局设置，只保证 LOD 阈值可观测。

## Sources

[1] Naval Encyclopedia — Lion class battlecruisers — https://www.naval-encyclopedia.com/ww1/uk/lion-class-battlecruisers.php (published 2016-05-22, accessed 2026-09-18)  
[2] worldwar1.co.uk — HMS Queen Mary — http://www.worldwar1.co.uk/battlecruiser/hms-queen-mary.html (published unknown, accessed 2026-09-18)  
[3] Unity Manual 2022.3 — LODGroup — https://docs.unity3d.com/2022.3/Documentation/Manual/class-LODGroup.html (accessed 2026-09-18)  
[4] Unity Manual 2022.3 — QualitySettings — https://docs.unity3d.com/2022.3/Documentation/Manual/class-QualitySettings.html (accessed 2026-09-18)  
[5] MaritimeQuest — HMS Queen Mary data — https://www.maritimequest.com/warship_directory/great_britain/battleships/queen_mary/hms_queen_mary_data.htm (published 2007-10-19, accessed 2026-09-18)  
[6] Naval Encyclopedia — HMS Tiger — https://www.naval-encyclopedia.com/ww1/uk/hms-tiger.php (published 2019-12-08, accessed 2026-09-18)  
[7] Unity Scripting 2022.3 — LODGroup.size — https://docs.unity3d.com/2022.3/Documentation/ScriptReference/LODGroup-size.html (accessed 2026-09-18)  
[8] Unity Manual 2022.3 — Frustum size at distance — https://docs.unity3d.com/2022.3/Documentation/Manual/FrustumSizeAtDistance.html (accessed 2026-09-18)  
[9] Unity Manual — Level of Detail — https://docs.unity3d.com/Manual/LevelOfDetail.html (accessed 2026-09-18)  
[10] URP 14 — Universal Render Pipeline Asset — https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@14.0/manual/universalrp-asset.html (accessed 2026-09-18)  
[11] historyofwar — Lion class — http://www.historyofwar.org/articles/weapons_lion_class_battlecruisers.html (published 2007-11-15, accessed 2026-09-18)  
[12] Unity Manual 2022.3 — Camera.layerCullDistances / Maximum LOD — https://docs.unity3d.com/2022.3/Documentation/ScriptReference/Camera-layerCullDistances.html ; https://docs.unity3d.com/2022.3/Documentation/Manual/class-QualitySettings.html (accessed 2026-09-18)  
[13] britishbattles — Jutland fleets — https://www.britishbattles.com/first-world-war/the-battle-of-jutland-part-i-the-opposing-fleets/ (accessed 2026-09-18)  
[14] Unity Scripting 2022.3 — LODGroup.ForceLOD — https://docs.unity3d.com/2022.3/Documentation/ScriptReference/LODGroup.ForceLOD.html (accessed 2026-09-18)  
[15] 本仓库复核 — queen_mary_v3/复核_2026-09-18.md（automatic 档 15 艘全 LOD0 的成因分析；非外部引用）  

完整逐条证据见 `research/queen-mary-refine-lod/findings/F1.md` … `F4.md`。
