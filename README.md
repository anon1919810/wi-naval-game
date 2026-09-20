# 《敌前转向》（Gefahrwend）· 一战舰船游戏资产

> 项目名取自 1916 年日德兰海战中舍尔的敌前转向（*Gefechtskehrtwendung*）——三次 180° 转向让公海舰队从英军战列线前脱险。
> 配套的自研舰船设计计算器叫 **[Plimsoll](docs/sps-replacement/SPEC.md)**（载重线）。
> 命名约定：**平台用历史意象命名，模块用方法命名**（`plimsoll.bonjean` / `.stability` / `.damage`）。

当前**玩法运行时**模型为 v4：`Assets/Prefabs/Ships/HMS_Queen_Mary_1913.prefab` 由 `queen_mary_v4/QueenMary_v4_Gameplay.fbx` 构建（`unity/Editor/ShipRuntimeBuilder.cs:190-203`，找不到 v4 时才回退到契约里的 v3 FBX）。v3 灰盒（`queen_mary_v3/queen_mary.py`，101 对象、85 网格、31,164 三角形）保留为历史资产与**契约数据来源**——碰撞代理、14 个舱室、LOD 剖面等仍从 `queen_mary_v3/` 读取。

**展示/剖视精修**位于 `queen_mary_v4/`（2026-09-19）：独立生成脚本、外观+内部 FBX、PBR 贴图与剖视副本；`historically_certified:false`。v4 **已**替换 Lab Prefab（commit `fdae103`）、**已**建 v4 LOD、**已**通过 Unity 验收 13/13 —— 见 [queen_mary_v4/README_精修资产.md](queen_mary_v4/README_精修资产.md) 与 `queen_mary_v3/runtime_acceptance/v4_unity_acceptance.json`。

观察与资源规划基准为 50–200 m、15 艘同屏；这不是硬性锁定游戏相机。

## 当前状态 · 2026-09-20

- **main**：最近一次玩法代码提交 `2794c80`（当前 HEAD 用 `git log -1` 查，文档提交会让 SHA 前进）→ https://github.com/anon1919810/wi-naval-game
- **入口交接（3D/后续模型）**：[交接_3D协作与试验场_2026-09-20.md](交接_3D协作与试验场_2026-09-20.md)
- 试验场：图鉴 UX + P2.5 破片/爆炸/穿板规则；EditMode 28/28；结果**不**直接作主战斗数值。
- GameplayLab：v4 外观 + A 阶段战斗正确性；射击仍为即时射线（B 阶段未做）。

- [交接 · 3D 协作与试验场 · 2026-09-20](交接_3D协作与试验场_2026-09-20.md)
- [交接 · 损伤试验场 · 2026-09-20](交接_损伤试验场_2026-09-20.md)
- [交接 · 战斗正确性 A · 2026-09-19](交接_战斗正确性A_2026-09-19.md)
- [v4 精修资产](queen_mary_v4/README_精修资产.md)
- [试验场图鉴](queen_mary_v3/damage_range/README_图鉴.md) / [P2.5 规则](queen_mary_v3/damage_range/README_P25规则.md)
- [v4 精修资产说明](queen_mary_v4/README_精修资产.md)
- [GameplayLab 操作与 T16 特效](queen_mary_v3/GAMEPLAY_LAB.md)
- [本轮详细成果、实测帧时间与限制](queen_mary_v3/运行时验收_2026-09-18.md)（**历史记录**）
- [本分支 LOD/精修订正说明](queen_mary_v3/LOD精修_2026-09-18.md)
- [独立复核：LOD 自动档成因、帧时间可信度](queen_mary_v3/复核_2026-09-18.md)（历史）
- [Unity 集成和复现命令](queen_mary_v3/unity/README_集成.md)
- [LOD 双相机剖面配置](queen_mary_v3/lod_profiles.json)
- [compose 特性规格](docs/compose/spec/model-refine-lod.md) / [combat-vfx](docs/compose/spec/combat-vfx.md)
- [最初交接与历史记录](交接文件_GPT6_2026-09-17.md)
- [v3 建模交接](queen_mary_v3/交接_v3.md)
- [精修素材清单](HMS_Queen_Mary_精修素材清单.md)

## 目录

| 路径 | 用途 |
|---|---|
| `queen_mary_v3/queen_mary.py` | v3 舰船生成脚本（GameplayLab 运行时资产来源） |
| `queen_mary_v3/unity/` | 唯一有效 Unity 玩法源码 |
| `queen_mary_v4/` | v4 模块化精修与剖视资产包（独立脚本与 FBX） |
| `queen_mary_v3/*.blend` / `*.fbx` | 当前运行时导入资产（v3） |
| `queen_mary_v3/unity/` | 唯一有效 Unity 源码目录 |
| `queen_mary_v3/runtime_acceptance/` | 12 张强制 LOD 图、碰撞/舱室验收、重复构建证据 |
| `queen_mary_v3/fleet_benchmark/` | 15 舰测试报告、截图、帧时间 CSV、可复现播放器 |
| `queen_mary_v3/unity_preview/` | 五张 URP 通常视角 |
| `queen_mary/` | 历史 v2，保留对照 |
| `queen_mary_v3/docs/legacy_codex_unity/` | 历史实现，不能同步进工程，否则类名冲突 |
| `D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval` | 当前舰船 Unity 工程：2022.3.62f3c1 / URP 14.0.12 |

## 构建与验证

```powershell
cd "C:/Users/杨睿/Desktop/HMS_Queen_Mary_建模成果_2026-09-17/queen_mary_v3"
.\rebuild.ps1
.\unity\verify_runtime.ps1 -ProjectPath "D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval" -Benchmark
```

Blender Store 启动器可能无输出，构建脚本核对新完成记录与文件时间戳。Unity 验证要真正运行编辑器编译和渲染，不能用“静态扫描没有报错”代替。

| 证据 | 本轮结果 |
|---|---|
| `verification.json` | 32 项几何 + 13 项设定/假设一致性检查通过；不代表史实认证 |
| `fbx_verification.json` | 18 项 FBX 往返通过 |
| `ship_runtime_build.json` | 模型为 v4 Gameplay；24 个隐藏的部件代理，24 盒 trigger + 1 船体凸 trigger，14 舱室；LOD0 62 渲染器/81,688 三角 · LOD1 17/81,688 · LOD2 17/61,264 · LOD3 1/59,408 |
| `runtime_acceptance/v4_unity_acceptance.json` | v4 三份 FBX 导入、节点、八炮口、材质等 13/13 通过（2026-09-19） |
| `runtime_acceptance/runtime_acceptance.json` | 12 张实际 LOD 图、进水容量、6 方向命中及舷外不命中通过 |
| `runtime_acceptance/repeat_build.txt` | 同进程重建两次，4 份生成网格 GUID 不变 |
| `unity_verification_urp.json` | 契约命名、1:1 尺度、舰艏 +Z、右舷 +X、炮塔轴与材质通过 |
| `unity_render_check.json` | 五张通常视角，品红、空白和取景检查通过 |
| `fleet_benchmark/fleet_benchmark.json` | 15 舰、1080p、五档离屏采样；限制见详细成果 |
| `fleet_benchmark_recheck_20260918/results2/fleet_benchmark.json` | 复核复跑：lodBias / 质量档位 / 逐船 LOD 比例入档，档位分布三次一致 |
| `integration_verification.json` / `unity_verification.json` | 上一轮继承与导入记录，保留历史用途；新鲜度以本轮报告为准 |

## 改动约定

保留数据驱动、模块命名、炮塔和炮管独立枢轴；不要把模型细节合并到不可独立驱动的层级。贴体结构从船体型值派生。旧版资产、历史交接与原始资料保留对照。
新增历史判断应带来源或标为估算。内部舱室、水下件当前作为系统代理关闭渲染；不能据此声称它们在所有视角都不可见。
下一阶段：真实游戏相机与 LOD 切换（阈值见 `lod_profiles.json` 双剖面）、火控/遮挡射界与转塔联动、取得型线图后的尺度校正。
LOD 生效阈值 = 剖面 `screenHeights` × 质量档 `lodBias`；`LODGroup.size` 用实测包围尺寸，不是舰长 213.4 m。1913 灰盒可见层精修（中烟囱圆形识别、上层建筑块面、副炮层带/步廊）见 `queen_mary.py` 与研究 `research/queen-mary-refine-lod/REPORT.md`。

- [损伤试验场交接 · 2026-09-20](交接_损伤试验场_2026-09-20.md)
