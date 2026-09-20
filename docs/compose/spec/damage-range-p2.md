---
feature: damage-range-p2
status: delivered
updated: 2026-09-20
branch: feature/damage-range-p2
commits: 4f19502..HEAD
---

# 试验场 P2 · 图鉴化与可观测

## Report

**What was built** — 损伤试验场图鉴化：`range_layout.json` 驱动装甲层/模块/8 条教学预设；`RangeLayout` + `RangeSolver` 优先读 Resources；`DamageRangeView` 重构为左图鉴+中剖视+右 Inspector（等效装甲、模块卡、Compare 副案、中文事件时间轴、导出 JSON、H 帮助）。供人类玩家当「图鉴」操作与观测；结果仍非主战斗数值。

**Verification** — EditMode **21/21 Passed**（`p2_tests/editmode_p2.xml`），含 `RangeLayoutTests`：layout 解析、Solver 使用 layout 模块、contact_vs_delay 双配置且延迟起爆时间更长。与 DamageRange/Sweep/Penetration 既有用例共存。

**Journey log** — (1) 图鉴预设放 JSON，改条目不必改 C#。(2) Compare 副案必须配置在 layout，不能由 UI 改写已算报告。(3) 等效装甲 mm 必须在 UI 标明是实验代理。(4) 中断后以 EditMode XML 为验收依据。

## [S1] Problem
试验场对人类不友好：缺预设、对照、模块说明与可观测时间轴。

## [S2] Design
layout JSON + Resources + View 三栏图鉴 UX；Solver 读 layout；原则「测中完善、不直用于主战斗」。

## [S3] Out of Scope
主战斗契约合并、史实认证、完整播放器美术。

## Tasks
- [x] T1 layout JSON + RangeLayout + Resources
- [x] T2 DamageRangeView 图鉴 UX
- [x] T3 RangeLayoutTests 3/3（总 EditMode 21/21）
- [x] T4 文档 README_图鉴.md + 证据 XML
