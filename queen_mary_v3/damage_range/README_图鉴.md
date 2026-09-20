# 损伤试验场 · 图鉴玩法说明（P2）

> 实验模型，`historically_certified: false`。结果**不可**直接当作主战斗装甲/交火数值。

## 打开

1. Unity 打开 `D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval`
2. `Tools → Naval → Open damage range`（或打开 `Assets/Scenes/DamageRange.unity`）
3. **Play** 进入图鉴界面

布局数据：`Assets/Resources/DamageRange/range_layout.json`（可改条目/预设，不必改 C#）。

## 界面（三栏）

| 区域 | 内容 |
|---|---|
| **左 · 图鉴条目** | 基线剖射 / 厚板挡弹 / 无装甲对照 / 接触vs延迟 / 大着角 / 高阻力材料 / 破片雨 / 高速撞击 — 点选即载入参数并开火 |
| **左 · 参数** | 板厚、材料、速度、角度、引信、破片等滑条；FIRE / Next seed / Compare |
| **中 · 剖段** | 3D 剖视；中键拖动环绕；剖视开关、破片路径 |
| **右 · Inspector** | 结果摘要、**等效装甲 mm**、**模块卡片**（直伤/爆/破片）、Compare 副案、**事件时间轴**（点击跳回放）、导出 JSON |

## 操作

| 键/操作 | 作用 |
|---|---|
| 左侧图鉴按钮 | 载入预设并 FIRE |
| **FIRE** | 按当前参数重算 |
| **Next seed** | 换随机种子再开火 |
| **Compare** | 对图鉴预设的 `compare_config` 再算一发（如接触 vs 延迟） |
| 事件列表点按 | 跳到该事件的回放进度 |
| 中键拖动 | 旋转视角 |
| Space | 回放 播放/暂停 |
| H | 操作说明显隐 |
| 导出 JSON | `last_shot.json` + 时间戳报告 |

## 事件中文对照

出膛 / 接触引信 / 穿透 / 被挡停 / 起爆 / 擦过设备 / 飞出剖段

## 模块卡片（试验 ID）

| ID | 界面名 | 说明 |
|---|---|---|
| Boiler_Room_1 | 锅炉舱（试验） | 中段路径易受擦伤 |
| Engine_Room_1 | 轮机舱（试验） | 后舱壁之后，厚壁降爆炸伤 |
| Feed_Pump | 给水泵（实验ID） | **非**主舰契约，检验破片偏置命中 |

## 验收证据

- EditMode XML：`queen_mary_v3/damage_range/p2_tests/editmode_p2.xml`（**21/21 Passed**，含 RangeLayoutTests 3 项）
- 因子扫描：`damage_range/sweeps/`（v1–v4；见 `README_扫描完善.md`）

## 通往可信战斗（原则）

图鉴/扫描 → 完善 RangeSolver → 数据表与事件契约 → 映射到 `ShipSystemsState` / `ShipHitResolver` → GameplayLab。  
**禁止**把 CSV 原样写进主战斗平衡表。
