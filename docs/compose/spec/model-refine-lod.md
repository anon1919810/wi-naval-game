---
feature: model-refine-lod
status: designed
updated: 2026-09-18
branch: feature/model-refine-lod
commits: <base-sha>..<head-sha>
---

# 模型精修与 LOD 阈值补全

## Report

## [S1] Problem

1. 灰盒在 50–200 m 中距的可读性主要靠剪影质量块（船体、三烟囱、四炮塔、上层建筑、单杆桅、舰尾步廊、副炮层带）。v3 已有细节，但缺少以识别特征为导向的可见层精修，且部分点未与 1913 口径对齐说明。
2. Unity LOD 屏幕高度阈值仍写死在 `ShipLodBuilder` 的 `0.20/0.08/0.03/0.01`；工程质量档 `lodBias` 常为 2，使生效阈值约为作者值的一半。舰队基准 automatic 档在现相机下 15 艘全落 LOD0，无法演示 LOD 切换，也无法服务不同相机剖面。
3. 阈值、`LODGroup.size`、`lodBias`、FOV、距离未形成可配置、可验收、可复现的一套系统。

## [S2] Design

### S2.1 史实/可见层约定

- 目标配置保持 **1913 服役原状灰盒**，`historically_certified` 仍为 `false`。
- **禁止**本轮引入：Tiger 布局、第五主炮塔、1914+ AA、三脚桅、型线数字重写、贴图/PBR。
- 可动硬约束不变：炮塔链 `Turret_* → Elevation_* → Barrel_*` 在 LOD0/1/2 保持独立变换；LOD3 才冻结。
- 新几何/比例改动必须在 `queen_mary.py` 中完成并可 `rebuild.ps1` 复现；非显然数字在 `SOURCES` 或对象属性上带 `source`/`estimate`。

研究结论（见 `research/queen-mary-refine-lod/REPORT.md`）允许的可见层精修点：

| 点 | 行为 | 标签 |
|---|---|---|
| 中烟囱识别 | `Funnel_2` 截面/体量相对前后烟囱更「圆」且略可辨（半径/环箍表达），不改烟囱高度拉齐结论 | source worldwar1 + estimate 比例 |
| 舰尾步廊 | 侧视/斜视轮廓保持可读；不作为远档优先丢弃件 | 既有 module |
| pole mast | 保持单杆+拉索；拉索服务中距剪影，不堆细线 | 既有 user/source |
| 副炮层带 | 单层 casemate 带连续可读；单门凹口可在远档简化 | source 单层 4" casemate |
| 上层建筑 | 块面/倒角服务中距「块状清晰」，不增加战斗语义合并 | estimate |
| 无 AA / 有网 | 数据与几何均保持 1913：无 AA，防雷网 stowed 在位 | source 1914-10 AA |

### S2.2 LOD 双相机剖面（可配置）

新增数据文件（资产侧，Unity 构建同步）：

`queen_mary_v3/lod_profiles.json`

```json
{
  "ship_id": "HMS_Queen_Mary_1913",
  "default_profile": "tactical_50_200m",
  "formula": "relH = lodGroupSize * lodBias / (2 * distance * tan(fovDeg/2 * pi/180))",
  "notes": [
    "screenHeights are authoring values for LOD.screenRelativeTransitionHeight",
    "recommendedLodBias is the intended QualitySettings.lodBias when using this profile",
    "Do not treat LODGroup.size as ship length; use measured group size"
  ],
  "profiles": [
    {
      "id": "tactical_50_200m",
      "description": "Tactical mid-range observation 50-200 m; keep silhouette massing",
      "screenHeights": [0.45, 0.18, 0.06, 0.02],
      "recommendedLodBias": 1.0,
      "expectedAt": [
        {"distance_m": 50, "fov_deg": 50, "expectedLod": 0},
        {"distance_m": 200, "fov_deg": 50, "expectedLod": 0}
      ]
    },
    {
      "id": "fleet_1_2km",
      "description": "Fleet-scale camera ~1-2 km; automatic LOD must span levels",
      "screenHeights": [0.40, 0.18, 0.07, 0.025],
      "recommendedLodBias": 1.0,
      "expectedAt": [
        {"distance_m": 1700, "fov_deg": 50, "expectedLod": 2},
        {"distance_m": 2500, "fov_deg": 50, "expectedLod": 2}
      ]
    }
  ]
}
```

C# 侧（`Naval` 运行时，JsonUtility 友好、无字典）：

- `ShipLodProfileAsset` / `ShipLodProfiles`：`id`, `description`, `screenHeights[4]`, `recommendedLodBias`, `expectedAt[]`。
- `ShipLodBuilder` **不再写死** `ScreenHeights`；构建时读取 profile（参数 `-lodProfile <id>` 或默认 `default_profile`）。
- `ShipDefinition` 增加：`lodProfileId`、`lodScreenHeights`、`lodRecommendedBias`、`lodGroupSizeMeasured`（若构建时可测；否则写 -1 并在 notes 说明）。
- `ShipFleetBenchmark`：报告写入 `lodProfileId`、`lodScreenHeights`、`lodGroupSizeUsed`（实例上实测 `LODGroup.size`）、`recommendedLodBias`；automatic 阶段 notes 解释用**当前 profile + 实测 size**，不把船长当 size。
- 验收不强制改工程 QualitySettings；允许报告记录「质量档 bias 与 profile recommendedLodBias 不一致」。

### S2.3 公式与标定

- 与现有基准一致：`relH = size * lodBias / (2 * d * tan(fov/2))`。
- 标定用 **实测 `LODGroup.size`**（`RecalculateBounds` 后读取），写入构建报告。
- 若实测 size 与研究示意值（≈船长）不同，**以实测为准**重算 expectedAt；spec 中 JSON 数值可按实测修订一次（Amendment），但剖面结构不变。

### S2.4 流程与证据

- 唯一 Blender 入口：`queen_mary_v3/queen_mary.py`；唯一 Unity 源：`queen_mary_v3/unity/`。
- 不同步 `docs/legacy_codex_unity`。
- 几何改动必须更新/接受 `geometry_sha256` 变化并写入报告；重复生成仍须通过。
- LOD 报告与文档不得把「子网格数」写成实测 draw call；帧时间只引用档位顺序与削减量级。

## [S3] Out of Scope

- 型线图接入与 `hull_offsets.json` 重算
- 火控/遮挡射界、穿深、浮力求解、损管、AI
- 第二艘船、战役内容
- GPU Resident Drawer / Cross Fade 管线全局改造（仅文档提示风险）
- 把研究报告升级为史实认证或改动 `historically_certified`

## Tasks

- [ ] T1: 实现 `lod_profiles.json` + `ShipLodProfiles` 解析与同步到 Unity Resources — acceptance: 文件存在且批处理构建日志/报告出现 profile id 与 4 个阈值 (covers: S2.2)
- [ ] T2: `ShipLodBuilder`/`ShipRuntimeBuilder`/`ShipDefinition` 改为按 profile 写 LOD 阈值并记录 profile/size — acceptance: `ship_runtime_build.json` 含 `lodProfileId`、`lodScreenHeights`，默认非硬编码旧四元组时能切换 profile (covers: S2.2, S2.3)
- [ ] T3: `ShipFleetBenchmark` 报告字段与 automatic notes 使用实测 size + 当前 profile — acceptance: 新基准 JSON 含 `lodProfileId`/`lodGroupSizeUsed`/`lodScreenHeights`/`lodBias`，notes 在「自动档未跨档」时解释成因 (covers: S2.2, S2.3)
- [ ] T4: `queen_mary.py` 灰盒可见层精修（中烟囱识别、上层建筑块面、副炮层带/步廊中距可读；禁止 AA/Tiger/三脚桅/型线重写） — acceptance: `rebuild.ps1` 通过；对象清单仍含 3 烟囱、pole mast、无 AA；新几何标签合规；`geometry_sha256` 变化已记录 (covers: S2.1)
- [ ] T5: 文档与交接 — acceptance: 根 README/集成 README 增加 LOD 剖面用法与研究路径；运行时验收或复核式说明引用新 profile 字段与限制 (covers: S2.1, S2.2, S2.4)
- [ ] T6: 验证 — acceptance: 可复现命令输出有记录（Blender 验证通过；Unity 若工程锁/环境不可用则明确 PRE-EXISTING/ENV 并保留报告字段检查） (covers: S2.4; depends: T1, T2, T3, T4)
