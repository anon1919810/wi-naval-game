# Research brief — T16 战斗 VFX 可读性

## Question

在一战拟真向灰盒海战 lab（Unity URP，15 艘上限，当前单舰+同模靶船）中，如何用**低成本**特效让玩家一眼看出：谁开火、弹往哪、是否命中、损伤程度？是否必须从灰盒升级到完整建模？

## Scope

**In** — 曳光/弹道观感、炮口闪光与烟、水花/近失、命中爆炸、损伤可视化（进水/系统）、占位音效设计原则、Unity 粒子在 URP 的成本注意点。

**Out** — 高模舰船、完整贴图管线、真实流体、联机同步特效、完整弹道学认证。

## Assumptions

- 日期：2026-09-19；深度：quick
- 工程：Unity 2022.3 URP 14；仓库 wi-naval-game / Desktop HMS_Queen_Mary 资产
- 特效以代码生成粒子/TrailRenderer 为主，不依赖商店资源
- 决策：L1 弹道/水花/爆炸 + L2 炮口 + L3 损伤 HUD/可视 + 占位音

## Angles

- **F1** — 海战/军事游戏公开的战斗可读性做法（tracer、splash、muzzle flash）
- **F2** — Unity URP 粒子/Trail 在多舰场景的性能与实现要点
- **F3** — 一战舰炮交战的视觉语言（外观印象，非认证弹道）

## Decision this research feeds

compose-next `combat-vfx`：ShipCombatVfx 挂点、效果时长/尺寸、HUD 损伤提示、何时不必做高模。
