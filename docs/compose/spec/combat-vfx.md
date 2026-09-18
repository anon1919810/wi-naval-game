---
feature: combat-vfx
status: delivered
updated: 2026-09-19
branch: feature/t16-combat-vfx
commits: 8613c99..baaedf9
---

# 战斗 VFX 可读性（T16）

## Report

**What was built** — GameplayLab 炮战特效层：`ShipCombatVfx` 用代码生成炮口闪光、短弧曳光、水花与命中爆炸；`ShipGunBattery` 开火路径统一调用 VFX（不再叠加旧 LineRenderer）；LabBuilder 在玩家舰与靶船挂 VFX。占位音频 `AudioClip` 可空。首轮特效过大/双曳光/Q·X 无特效已回调（细曳光、每开火管均炮口、并发上限 16）。Unity **无第一方海战材质包**；本轮不引商店资源。

**Verification** — 脚本同步 `Assets/Scripts/Naval/ShipCombatVfx.cs`；用户 Play 反馈驱动两轮缩放与 Q/X 修复（`96d86e2` → `22c5293` → `57e2ea9` → `baaedf9`）。完整 `verify_runtime -Benchmark` 未在本分支重跑（Unity 编辑器常驻占锁）；以工程内编译 + 手动 Play 为准。

**Journey log** — (1) 213 m 舰体上粒子 startSize 数米级会像橙色色块。(2) 曳光若画到 shellRange 会变「天际激光」，须视觉截断。(3) 开火链路勿 SpawnTracer+PlayTracer 双轨。(4) 后炮塔无特效先查 ARC SKIP，再查 tracer/muzzle 预算。(5) 商店海面/材质包另任务，与战斗可读性解耦。

## [S1] Problem

开火像激光、无炮口/水花/爆炸，损伤只有文字；后炮塔曾无特效。

## [S2] Design

- **L1** 弧线曳光（≤900 m 视觉）、miss 水花、命中爆炸（穿透更亮）
- **L2** 每根开火炮管炮口闪光
- **L3** 命中后目标渲染器短暂变暗 + HUD 命中文本
- API：`ShipCombatVfx.PlayTracer/PlayMuzzle/PlaySplash/PlayImpact`；`FindOrGlobal`/`EnsureOn`
- 音效占位：clip 空则静音一次日志

## [S3] Out of Scope

高模舰船、商店海战包、真实弹道认证、联机特效、完整音频设计。

## Tasks

- [x] T1: ShipCombatVfx API
- [x] T2: ShipGunBattery 接入
- [x] T3: Lab 两舰挂 VFX
- [x] T4: 回调尺度/去双曳光/Q·X 炮口 + 文档（GAMEPLAY_LAB.md）
