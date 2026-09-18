# Queen Mary Unity 集成 · 2026-09-18

唯一源码目录为本目录的 `Editor/` 与 `Scripts/`。用 `sync_to_unity.ps1` 同步；不要同步 `docs/legacy_codex_unity`。
当前工程 `D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval`，Unity 2022.3.62f3c1，URP 14.0.12。

## 使用

```powershell
.\verify_runtime.ps1 -ProjectPath "D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval" -Benchmark
```

省略 `-Benchmark` 只重建与验证。`-OutputDirectory` 可指定报告目录，默认为资产目录的 `runtime_acceptance`。
脚本会启动 Unity 批处理，编译脚本、构建预制体两次、验证 GUID、碰撞和 LOD 图像，再验证轴向、契约和通常视角。
不要与同一工程已打开的编辑器同时运行。URP 首次配置或材质更新时运行菜单 `Tools/Naval/Set up URP`。

| 入口 | 作用 |
|---|---|
| `ShipRuntimeBuilder.BuildBatch` | 生成预制体、舱室、船体代理、LOD 和 ShipDefinition |
| `ShipRuntimeAcceptance.RebuildAndTestBatch` | 两次构建 + 真实碰撞/舱室/12 张 LOD 图验证 |
| `ShipDeliveryChecks.RunBatch` | 契约/轴向/材质检查 + 五张通常视角 |
| `ShipBenchmarkBuilder.BuildBatch` | 构建 15 舰离屏基准播放器 |
| `ShipGameplayLabBuilder.BuildBatch` | 生成可玩 GameplayLab 场景（T5/T6/T7 原型） |

以上类均位于 `Naval.EditorTools` 命名空间；批处理参数为 `-executeMethod Naval.EditorTools.<入口>`。
报告落点可用 `-shipReportDirectory <目录>` 设置，未传参时为当前工作目录的 `ShipAcceptance/`。

## 运行时资产契约

- 模型 1:1，Unity +X 右舷、+Y 向上、+Z 舰艏，水线 Y=0。舰长 213.4 m、舰宽 27.2 m、吃水 9.9 m。
- 四炮塔的偏航实测为节点局部 +Z，正角转右舷；俯仰实测为节点局部 +X，正角抬炮口。不要按 Unity 世界轴猜测子节点的局部轴。
- FBX 名称与 JSON 引用从 `ship_contract.unity.json` 读取，现已包含 `buoyancy_compartments` 与 `lod_profiles`。
- 预制体路径 `Assets/Prefabs/Ships/HMS_Queen_Mary_1913.prefab`，定义位于 `Assets/Resources/Ships/HMS_Queen_Mary_1913/`。
- **LOD 阈值**来自 `lod_profiles.json`（默认 `tactical_50_200m`，另有 `fleet_1_2km`）。`ShipLodBuilder` 不写死阈值；`ship_runtime_build.json` 与 `ShipDefinition` 记录 `lodProfileId` / `lodScreenHeights` / `lodRecommendedBias` / `lodGroupSizeMeasured`。生效阈值 = 作者阈值 × `QualitySettings.lodBias`。批处理可加 `-lodProfile fleet_1_2km` 切换剖面。
- 14 个 `ShipCompartment` 挂上体积、渗透率和可进水体积。它们是系统参数载体，尚未实现完整动态浮力/损管。
- 24 个内部/水下代理关闭 MeshRenderer 并使用盒 trigger；另有 `Hull_Collision_Proxy` 粗凸包 trigger。选中/粗筛射线须使用 `QueryTriggerInteraction.Collide`，可按父节点区分船体代理与部件。
- 炮塔链在 LOD0/1/2 中保持独立变换；LOD3 为冻结的静态远景。合并网格按材质，不能把 renderer 数或子网格数写成实测 draw call。

## 验收与证据

最新数量、LOD 成本、性能数据、截图和限制请读 [本轮验收](../运行时验收_2026-09-18.md)。
LOD0/1/2/3 全舰三角形数为 29,264 / 29,264 / 16,344 / 14,488；渲染器数为 61 / 17 / 17 / 1。
旧 4,990 面剪影曾漏掉几何，旧近景截图也未覆盖远档；这些结论已被本轮真实图像验收替代。
隐藏窗口会使屏幕绘制被跳过，不能直接报告此时的循环帧率。基准改为显式离屏绘制并等 GPU 完成，因此报告的是包含同步开销的资产渲染基准，不是整款游戏 FPS。

旧说明已保存在 `docs/Unity集成_2026-09-18_更新前.md`，用于追溯早期方案与轴向调查。
