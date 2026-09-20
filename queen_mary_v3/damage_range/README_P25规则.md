# P2.5 · 破片 / 爆炸 / 穿板规则（实验）

> 仍为**实验代理**，`historically_certified: false`。不可直接当主战斗数值。

## 新增规则

| 规则 | 行为 |
|---|---|
| **穿板行程** | `plate_transit` 事件：`路径≈板厚/|dir.x|`，时间≈路径/当前速度；延迟引信含穿板时间 |
| **爆炸位置分类** | 起爆点在设备盒内 → `detonation: inside_module:ID`；舱内爆对该模块 **blast bonus**（默认 1.8×，上限 0.65） |
| **破片物理量** | 每条破片有 `massKg / speedMps / energyJ`（种子扰动）；模块破片伤按 **能量归一 × 剩余穿深比** 累积 |
| **开放爆前向偏置** | 非舱内爆时破片方向沿弹道轻微偏置 |
| **配置** | `fragmentMassG`、`fragmentVelocityMps`、`blastInsideBonus`、`modelPlateTransit`（Validate 有界） |

## 图鉴 UI

- 事件中文增加 **「穿板行程」**
- 模块卡上方显示破片条数 / 命中数 / 能量合计

## 测试

`DamageRangeP25Tests`：穿板事件有/无、破片质量速度能量、起爆 locus、舱内爆上限、seed 能量差、含穿板后事件时间单调。

## 仍未做

真实压力/进水/火灾、破片实体碰撞、跳弹、与主战斗 `ShipHitResolver` 合并。

## 验收

EditMode XML 见 `damage_range/p25_tests/`（以本次运行为准）。
