---
feature: model-refine-lod
status: delivered
updated: 2026-09-18
branch: feature/model-refine-lod
commits: a509954..be6be58
---

# 模型精修与 LOD 阈值补全

## Report

**What was built** — LOD 阈值从 C# 写死改为数据驱动：`queen_mary_v3/lod_profiles.json` 提供 `tactical_50_200m`（0.45/0.18/0.06/0.02）与 `fleet_1_2km` 双剖面；`ShipLodProfile.cs` + `ShipLodBuilder`/`ShipRuntimeBuilder`/`ShipDefinition`/`ShipFleetBenchmark` 读取剖面，报告记录 `lodProfileId`、`lodScreenHeights`、`lodRecommendedBias`、实测 `lodGroupSizeMeasured/Used`（213.40 m）与公式；批处理支持 `-lodProfile <id>`。Blender 灰盒可见层精修：Funnel_2 圆形识别环烘进网格、舰桥/艉部块面带并入 `Deck_Visual_Details`（装饰对象预算未破）；`geometry_sha256` 从 `5b248d11…` 变为 `9d6d6a76…`。历史验收文档已加「旧基线」横幅，当前口径见 `queen_mary_v3/LOD精修_2026-09-18.md`。

**Verification** — `rebuild.ps1 -SkipRender`：32 geometry + 13 assumption + 18 FBX PASS；`verify_lod_profiles.py` → `lod_profile_math_ok`；Unity `ShipRuntimeBuilder.BuildBatch` → `ship_runtime_build.json` passed（剖面 tactical，阈值 0.45/0.18/0.06/0.02，size 213.40，24 关渲染 / 25 碰撞 / 14 舱室）；舰队基准重跑 → `fleet_benchmark_lod_profile_20260918.json` status completed，含全部 LOD 剖面字段；automatic 15 艘全 LOD1（质量档 lodBias=2），forced 档位顺序 LOD0>1>2>3（帧时间仅作顺序参考）。独立复核 critical 两项均 PASS。

**Journey log** — (1) 新装饰不能单独建对象：必须并进 Funnel_2 / 既有合并装饰，否则 decoration>10 与 render meshes>65 会红。(2) Unity `LODGroup.size` 实测≈213.4 m（包围最长轴），不要按甲板高度估阈值距离。(3) 舰队基准 automatic 同档是编队纵深+相机距离的公式结果；新战术剖面把结果从全 LOD0 推到全 LOD1，跨档演示仍要调场景或用 `fleet_1_2km`。(4) 历史 `运行时验收`/`复核`/manifest 与新几何哈希会矛盾，必须加 superseded 横幅而不是改写历史。(5) 工作曾因没电中止；恢复检查点在 `model-refine-lod_RESUME.md`。

## [S1] Problem

1. 灰盒在 50–200 m 中距的可读性主要靠剪影质量块。v3 缺少以识别特征为导向的可见层精修说明。
2. Unity LOD 阈值写死在 `ShipLodBuilder` 的 `0.20/0.08/0.03/0.01`；质量档 `lodBias` 常为 2，舰队 automatic 全落 LOD0。
3. 阈值、`LODGroup.size`、`lodBias`、FOV、距离未形成可配置、可验收、可复现的系统。

## [S2] Design

### S2.1 史实/可见层约定

- 保持 **1913 服役原状灰盒**，`historically_certified: false`。
- 禁止：Tiger 布局、第五主炮塔、1914+ AA、三脚桅、型线数字重写、贴图/PBR。
- 炮塔链在 LOD0/1/2 保持独立变换；LOD3 才冻结。
- 改动在 `queen_mary.py`，可 `rebuild.ps1` 复现；非显然数字带 `source`/`estimate`。
- 装饰角色对象 ≤10、可渲染网格 ≤65；识别环/块面带并入既有网格。

| 精修点 | 行为 | 标签 |
|---|---|---|
| 中烟囱识别 | Funnel_2 截面 3.55×3.55 圆形 + 网格内识别环 | source ww1 + estimate |
| 舰尾步廊 / pole mast / 副炮层带 / 无 AA / 有网 | 维持 1913 | 既有 source |
| 上层建筑块面 | 并入 Deck_Visual_Details | estimate |

### S2.2 LOD 双相机剖面

`queen_mary_v3/lod_profiles.json`：

- `tactical_50_200m`：`[0.45, 0.18, 0.06, 0.02]`，bias 1
- `fleet_1_2km`：`[0.40, 0.18, 0.07, 0.025]`，bias 1

C#：`ShipLodProfiles`/`ShipLodProfile`；`ShipLodBuilder` 读 profile；`ShipRuntimeBuilder.Build(string)` + `BuildBatch` 解析 `-lodProfile`；`ShipDefinition` 与 `ShipFleetBenchmark` 记录 profile/size/formula。

### S2.3 公式与标定

`relH = size * lodBias / (2 * d * tan(fov/2))`。用实测 `LODGroup.size`（本资产 ≈213.40 m，包围最长轴）。质量档 `lodBias` 与作者阈值叠加时报告两者。

### S2.4 流程与证据

- Blender 源：`queen_mary_v3/queen_mary.py`；Unity 源：`queen_mary_v3/unity/`。
- 不同步 `docs/legacy_codex_unity`。
- 记录 `geometry_sha256`；子网格数 ≠ draw call；帧时间只引用档位顺序。
- 旧验收用历史横幅指向 `LOD精修_2026-09-18.md`。

## [S3] Out of Scope

- 型线图 / 火控 / 损管 / AI / 第二艘船
- GPU Resident Drawer / Cross Fade 全局改造
- 史实认证升级
- 本轮 `fleet_1_2km` 运行时重建验收（CLI 已支持）

## Tasks

- [x] T1: `lod_profiles.json` + `ShipLodProfiles` + Unity 同步 — acceptance: 构建报告含 profile id 与 4 阈值 (covers: S2.2)
- [x] T2: Builder/Runtime/Definition 按 profile 写阈值并记录 — acceptance: `ship_runtime_build.json` 含 `lodProfileId`/`lodScreenHeights`/`lodGroupSizeMeasured` (covers: S2.2, S2.3)
- [x] T3: FleetBenchmark 报告剖面字段与 notes — acceptance: `fleet_benchmark_lod_profile_20260918.json` 含 `lodProfileId`/`lodGroupSizeUsed`/`lodScreenHeights`/`lodFormula`/`lodBias` (covers: S2.2, S2.3)
- [x] T4: `queen_mary.py` 灰盒可见层精修 — acceptance: Blender 验证通过；3 烟囱/pole mast/无 AA；`geometry_sha256=9d6d6a76…` (covers: S2.1)
- [x] T5: 文档与交接 — acceptance: README/集成/LOD精修/历史横幅 (covers: S2.1, S2.2, S2.4)
- [x] T6: 验证 — acceptance: rebuild + math log + Unity build + benchmark JSON 有记录 (covers: S2.4; depends: T1–T4)
