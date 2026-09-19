# HMS Queen Mary · 一战舰船游戏资产

当前**玩法运行时**资产位于 `queen_mary_v3/`：Blender 程序化灰盒，101 对象、85 网格、31,164 三角形，已接入 Unity URP（GameplayLab 仍用此版 Prefab）。

**展示/剖视精修**位于 `queen_mary_v4/`（2026-09-19）：独立生成脚本、外观+内部 FBX、PBR 贴图与剖视副本；`historically_certified:false`，**未**替换 Lab Prefab，**未**做 v4 LOD / Unity 实机验收。详见 [queen_mary_v4/README_精修资产.md](queen_mary_v4/README_精修资产.md)。

观察与资源规划基准为 50–200 m、15 艘同屏；这不是硬性锁定游戏相机。

## 当前状态 · 2026-09-19

- **玩法**：T5–T16 GameplayLab（进水/射界/相机/穿深/靶船/鼠标群炮/战斗 VFX）已并入 master → `wi-naval-game/main`（`f717c0c` 起）。
- **模型**：v3 灰盒仍在运行时；v4 模块化精修包已入库，待 Unity 接入与战斗正确性（A 阶段）并行评估。
- **规划**：A 阶段战斗正确性计划见 Codex 目录 `docs/superpowers/plans/2026-09-19-queen-mary-combat-correctness.md`。

- [玩法原型交接 · 2026-09-19](交接_玩法原型_2026-09-19.md)
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
| `ship_runtime_build.json` | 24 个隐藏的部件代理，24 盒 trigger + 1 船体凸 trigger，14 舱室 |
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
