# 恢复检查点 · model-refine-lod · 2026-09-18

> 用户因电脑没电中止。**恢复时：若本回合无 Compose Next 指令，先重新加载 `compose-next` 技能再继续。**
> 工作区：`C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\.worktrees\model-refine-lod`
> 分支：`feature/model-refine-lod`（基线 master @ a509954；**改动尚未 commit**）

## 已完成（有证据）

| 项 | 证据 |
|---|---|
| deep-research 报告 | `research/queen-mary-refine-lod/REPORT.md` + findings F1–F4（在**仓库根**，不在 worktree） |
| LOD 双剖面 JSON | `queen_mary_v3/lod_profiles.json` |
| C# 解析与构建接入 | `ShipLodProfile.cs`、`ShipLodBuilder`/`ShipRuntimeBuilder`/`ShipDefinition`/`ShipFleetBenchmark` |
| `-lodProfile` CLI | `ShipRuntimeBuilder.BuildBatch` 读命令行参数 |
| Blender 精修 + 验证 | `rebuild.ps1 -SkipRender` 通过；`geometry_sha256=9d6d6a765993487ef4e0112ea217cad8e48642a51dab8482a31e2a36189df7c0` |
| Unity 运行时构建 | `runtime_acceptance/ship_runtime_build.json`：passed，剖面 `tactical_50_200m`，阈值 0.45/0.18/0.06/0.02，`lodGroupSizeMeasured=213.40` |
| 离线 LOD 数学 | `runtime_acceptance/verify_lod_profiles.log` → `lod_profile_math_ok` |
| 文档/历史澄清 | `LOD精修_2026-09-18.md`；验收/复核/manifest 已加「历史基线」说明 |
| 独立 review | 已完成；critical 为「证据陈旧 + 舰队基准字段未跑出」——文档侧已修，基准未跑 |

## 恢复后待办（按序）

1. 重新加载 **compose-next** 技能。
2. 将 worktree 内 `Assets` 侧已同步的最新 `.cs` / `lod_profiles.json` 再确认一次（Unity 工程 `D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval`）。
3. **T3 证据**：跑舰队基准使 `fleet_benchmark.json` 含 `lodProfileId` / `lodGroupSizeUsed` / `lodScreenHeights` / `lodFormula`：
   ```powershell
   cd "...\.worktrees\model-refine-lod\queen_mary_v3\unity"
   .\verify_runtime.ps1 -ProjectPath "D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval" -Benchmark
   ```
   或仅重建播放器后 `fleet_benchmark\run_benchmark.ps1`。**务必先确认编辑器已关、电量充足。**
4. （可选）用 `-lodProfile fleet_1_2km` 再建一次运行时船，验证舰队剖面写入报告。
5. 更新 `docs/compose/spec/model-refine-lod.md`：勾选任务、`status: delivered`、填 Report 与 commits。
6. 处理 review 非关键项：`integration_verification.json` 哈希注记、research 相对链接等。
7. **不要自动 merge**；提交/合并需用户确认（worktree `feature/model-refine-lod`）。

## 禁止再犯的坑

- 装饰件不能新建对象（预算：装饰角色 ≤10，可渲染网格 ≤65）——识别环/块面带必须并进 Funnel_2 / `Deck_Visual_Details`。
- `LODGroup.size` 实测约 213.4 m（包围最长轴），标定用实测值。
- 历史验收文档里的 `5b248d11…` 是旧基线，当前是 `9d6d6a76…`。
- 帧时间引用档位顺序，不引用单次 ms。
- 不要同步 `docs/legacy_codex_unity`。

## 关键路径速查

- 规格：`.worktrees/model-refine-lod/docs/compose/spec/model-refine-lod.md`
- 当前验收说明：`.worktrees/model-refine-lod/queen_mary_v3/LOD精修_2026-09-18.md`
- 构建报告：`.worktrees/model-refine-lod/queen_mary_v3/runtime_acceptance/ship_runtime_build.json`
