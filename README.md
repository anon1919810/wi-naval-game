# HMS Queen Mary · 一战舰船游戏资产

当前版本位于 `queen_mary_v3/`：Blender 程序化灰盒，101 对象、85 网格、31,164 三角形，已接入 Unity URP。它以 1913 年早期外观为目标，保留估算说明，`historically_certified:false`。
观察与资源规划基准为 50–200 m、15 艘同屏；这不是硬性锁定游戏相机。

## 当前状态 · 2026-09-18

已完成本轮交接中的运行时缺口：船体碰撞代理、14 个舱室数据、LOD0–3 实际图像验收和 15 艘同屏离屏渲染基准。修复了远档船体不显示、剪影丢几何及重复构建网格引用问题。
**feature/model-refine-lod（2026-09-18）**：灰盒可见层精修 + LOD 双剖面配置；`geometry_sha256` 已变为 `9d6d6a765993487ef4e0112ea217cad8e48642a51dab8482a31e2a36189df7c0`（上一基线 `5b248d11…` 见历史验收文档）。LOD 阈值改为读取 `queen_mary_v3/lod_profiles.json`。

- [本轮详细成果、实测帧时间与限制](queen_mary_v3/运行时验收_2026-09-18.md)（**历史记录**：几何与旧阈值以 2026-09-18 上午验收为准）
- [本分支 LOD/精修订正说明](queen_mary_v3/LOD精修_2026-09-18.md)
- [独立复核：LOD 自动档成因、帧时间可信度](queen_mary_v3/复核_2026-09-18.md)（历史）
- [Unity 集成和复现命令](queen_mary_v3/unity/README_集成.md)
- [LOD 双相机剖面配置](queen_mary_v3/lod_profiles.json)（战术 50–200 m / 舰队 1–2 km）
- [精修与 LOD 研究报告](../research/queen-mary-refine-lod/REPORT.md)（位于仓库根 `research/`，不在本 worktree 内）
- [compose 特性规格](docs/compose/spec/model-refine-lod.md)
- [最初交接与历史记录](交接文件_GPT6_2026-09-17.md)
- [v3 建模交接](queen_mary_v3/交接_v3.md)
- [精修素材清单](HMS_Queen_Mary_精修素材清单.md)

## 目录

| 路径 | 用途 |
|---|---|
| `queen_mary_v3/queen_mary.py` | 唯一舰船生成脚本，修改后重建 |
| `queen_mary_v3/*.blend` / `*.fbx` | 当前模型与 Unity 导入资产 |
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
