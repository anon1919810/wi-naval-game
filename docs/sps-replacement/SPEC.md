# Plimsoll · 舰船设计计算器规格

> 本文保留早期需求与七页参考字段，供迁移和覆盖核对使用。
> 当前批准范围以 [Plimsoll 1.0 规格](../plimsoll-1.0/spec.md) 为准，实际进度见 [当前状态](../plimsoll-1.0/current-status.md)。
> 目标是可脚本化、可验证、可追溯的舰船设计分析工具；未经同输入对照，不宣称比 SpringSharp 更准确。
> 参考界面图见 `docs/sps-reference/`。下文旧 schema、案例数字和模块路线不覆盖新的项目契约。

---

## 0. 命名与代号

| 对象 | 名称 | 说明 |
|---|---|---|
| **本软件** | **Plimsoll** | 载重线。船壳上那道刻线表示"不可逾越的载重限度"。取它是因为一个**设计校验工具**干的正是这件事。目录/包名小写 `plimsoll`，正文显示名 `Plimsoll` |
| **所属游戏** | **《敌前转向》（Gefahrwend）** | 指 1916 年日德兰海战中舍尔执行的敌前转向（历史上称 *Gefechtskehrtwendung*，三次 180° 转向使公海舰队脱险）。游戏本体的名称与边界见仓库根 README |

**命名架构**（新增模块时照此办理）：

> **平台用历史意象命名，模块用方法命名。**

于是 `plimsoll.hydrostatics`（静水力）、`plimsoll.bonjean`（Bonjean 曲线／几何法）、
`plimsoll.stability`（大角稳性 GZ）、`plimsoll.damage`（破损稳性）。
游戏侧同理：主标题用意象，战役与模式用术语。

---

## 1. 定位与边界

**是什么**：一套 1850–1950 年火炮战舰的设计与静水力计算核心，输入 JSON、输出 JSON，
可被脚本、CI、游戏引擎直接调用。附一个现代 Web 界面（后置）。

**不是什么**：不是 SpringSharp 的分支、移植或改写；不包含它的任何代码；
不声称历史认证（沿用 `historically_certified: false` 与 `estimate` 标注纪律）。

**独立实现的技术选择**：Plimsoll 使用自己的 Python 计算核心、公开说明的
输入输出契约和本地界面，便于批量分析、测试与游戏数据导出。参数化方法和型线积分
各有输入与离散误差；选择型线方法本身不证明对实际舰船更准确。

七页参考图用于字段需求盘点。完整的 SpringSharp 版本能力、内部算法和同输入结果
尚未逐项核验，不由截图推断其未提供的能力。参考图归档于 `docs/sps-reference/*.png`。

---

## 2. 架构原则（不可违反）

1. **核心是纯函数**：`input json → output json`。核心不得 import 任何 GUI、Unity、网络库。
2. **一切参数表都是外部 JSON**，用户可增删改：炮、弹、装甲、主机、船型系数。
3. **零隐藏常量**：核心代码里不出现没有来源的魔数；每个系数要么来自输入 JSON，
   要么来自带引用的公式实现。
4. **每个输出字段可溯源**：结果 JSON 中每一项附 `formula` / `source` / `estimate` 标记。
5. **确定性**：同输入必得同输出；用固定种子做抽样（如破损稳性场景）。
6. **可回归**：任何公式改动都要能通过靶船对照表（见 §7）。
7. **通用性契约（2026-09-22 用户指令）**：**Plimsoll 是通用求解器，能解任何船、任何设定；
   Queen Mary 只是案例，不是前提。**
   - 核心模块（hydrostatics/geometric/geometry/offsets/weights/armour/guns/freesurface/damage/cli）
     不得出现任何具体船只的字面常量或仓库路径 —— 由 `test_generic_ship.py` 的源码扫描把守；
   - 每艘船的全部专属数据都在自己的案例 JSON（含型线 `offsets_path`）里；
     型线是 `plimsoll-offsets-1` JSON，CLI 只认案例声明或 `--offsets`，不扫描仓库、不回落生成脚本；
   - per-ship 生成器（`tools/gen_*.py`）是**数据适配器**，不属于核心，允许读项目模型文件；
   - 通用性必须有活证据：`cases/generic_test_steamer_1910.json`（非 QM 的解析船）
     全链路测试通过 —— 至少保留一艘非史实/非本项目的靶船。

---

## 3. 数据模型

### 3.1 输入 `ship.json`

以下是旧 `plimsoll-ship-1` 设计示例，数字不作为当前 Queen Mary 史实验收值。
新项目使用 [data-contract.md](../plimsoll-1.0/data-contract.md) 的
`plimsoll-project-1`；单位、来源、加载工况和迁移以该契约及实际案例为准。

```jsonc
{
  "schema": "plimsoll-ship-1",
  "name": "HMS Queen Mary",
  "country": "United Kingdom",
  "type": "battlecruiser",
  "dates": { "laid_down": 1911, "launched": 1912, "completed": 1913 },
  "units": "SI",                       // 内部一律 SI，界面层负责换算
  "hull": {
    "lwl_m": 205.7,                    // 水线长
    "loa_m": 214.4,                    // 总长
    "beam_m": 27.1,
    "draught_normal_m": 8.5,
    "draught_deep_m": 9.9,
    "block_coeff": 0.551,              // Cb
    "waterplane_coeff": 0.80,          // Cwp（可推、可覆盖）
    "midship_coeff": null,             // Cm
    "prismatic_coeff": null,           // Cp = Cb / Cm
    "displacement_normal_t": 26770,
    "displacement_deep_t": 31650,
    "sources": { "lwl_m": "Tyne Built Ships 675.0 ft",
                 "block_coeff": "derived: 26770 t ÷ (205.7·27.1·8.5·1.025)" }
  },
  "hull_geometry": null,               // 可选：offsets / stations，见 §6.1
  "freeboard": { /* §5.2 */ },
  "guns": [ /* §5.3 */ ],
  "weapons": { /* §5.4 */ },
  "armour": { /* §5.5 */ },
  "machinery": { /* §5.6 */ }
}
```

### 3.2 输出 `result.json`

```jsonc
{
  "schema": "plimsoll-result-1",
  "ship": "HMS Queen Mary",
  "computed_utc": "...",
  "hydrostatics": { "displacement_t": ..., "awp_m2": ..., "tpc_t_per_cm": ...,
                    "kb_m": ..., "bm_m": ..., "gm_m": ..., "roll_period_s": ... },
  "trace": [ { "key": "awp_m2", "value": 4459.3,
               "formula": "Lwl · B · Cwp", "source": "standard hull-form approximation" } ],
  "warnings": ["Cwp not supplied; assumed 0.80 (estimate)"],
  "historically_certified": false
}
```

---

## 4. 模块划分

核心按计算域拆分为互不依赖的模块，恰好对应 SpringSharp 的标签（作为覆盖度检查表）：

| 模块 | 对应标签 | 职责 |
|---|---|---|
| `hull` | Hull | 主尺度、系数一致性、排水量 |
| `freeboard` | Freeboard | 舷弧/干舷剖面、甲板长度分配 |
| `guns` | Guns | 炮组、弹药、座圈与装甲重量 |
| `weapons` | Weapons | 鱼雷、水雷、深弹、杂项重量 |
| `armour` | Armour | 装甲带/甲板/舱壁/炮座/司令塔 |
| `machinery` | Engines | 锅炉、主机、功率、燃油/煤 |
| `performance` | Performance | 稳性、耐波性、抗损、成本、强度 |
| **`hydrostatics`** | （SpringSharp 无独立页） | **静水力曲线、GZ 曲线 —— 我们的差异化** |

---

## 5. 字段清单（自参考界面逐项抄录）

> 用途是**覆盖度检查**：实现时逐项确认"做 / 不做 / 为什么不"。
> 未列出的界面元素表示本轮未捕获，实现前需补。

### 5.1 Hull（`00_Hull.png`）
- Ship：Name、Country、Type、Year、Ship laid down、Engine built
- Dimensions：单位下拉（feet/metres）；Length（Waterline、Overall）；Beam（Hull、Bulges）；
  Draught (hull only)（Normal、Max）
- Displacement：船型滑条（Destroyer↔Cruiser↔Battleship↔Merchant hullform）；
  Block Coeff 刻度 0.40 Fine / 0.50 / 0.60 Full / 0.70 / 0.80 / 0.90 Solid / 1.00；
  Block coefficient（Normal、Max）；Displacement（Normal、Max）
- 派生显示：Waterplane area（sq ft / sq m）、Wetted surface area、Length:Beam、Natural Speed

### 5.2 Freeboard（`01_Freeboard.png`）
- 甲板型：Flush deck / Mid break；Save Picture…
- 剖面示意图标注：Quarter deck / Aft deck / Forward deck / Forecastle / Vitalspace
- Length (% of Lwl)：Forecastle、Fore Deck、Aft Deck、Quarter Deck
- Freeboard – Forward / – Aft：各 4 行
- 船首型（Normal bow…）、Depth Unlocked、船艉型（Cruiser stem…）
- Waterline length (Lwl)、Bow Angle (+ve = fore)、Ram Length、Stern overhang、Length OA
- Average freeboard

### 5.3 Guns（`02_Guns.png`）
- 子页：Summary / Main Battery / 2nd / 3rd / 4th / 5th Battery
- Batteries：五组「No N Battery」按钮；Lock/Unlock all shell weights
- Weights 表：行 = Guns / Mounts / Armour / Total (t) / Broadside (lbs) / Broadside (kg) /
  Magazine (t)；列 = Main / 2nd / 3rd / 4th / 5th / Total

### 5.4 Weapons（`03_Weapons.png`）
- Main / 2nd Torpedoes：Number、Sets、Diameter、Length、安装方式、重量
- Mines：Number、Reloads、Weight、布放方式
- Main / 2nd DC/AS Mortars：同上 + 布置方式
- Misc weight (t)：Hull–Below water、Hull–Above water、On deck、Above Deck、Void weight
- Hull space / Deck space

### 5.5 Armour（`04_Armour.png`）
- Armour：最大厚度单位下拉
- Belts & Bulkheads：默认档
  表：行 = Main / Ends / Upper / Bulge / Torpedo bulkhead；
      列 = Max Thickness、Length (ft)、Height (ft)、Weight (tons)；Total weight
- Main belt incline、Beam between bulkheads
- Type（Additional bulkheads…）
- Guns（见 Guns 页）
- Armour deck：Forecastle / Fore & aft decks / Quarter deck；覆盖方式下拉
- Conning towers：Forward、Aft；Total armour
- 示意图：Void weight / Armour deck

### 5.6 Engines（`05_Engines.png`）
- Speed & Power：Max speed（滑条）、Cruise speed、No. of shafts；
  Max/Cruise 两行的 Friction resistance、Wave resistance、Power to wavemaking、
  Power (hp)、Power (kW)
- Engines 复选框：Coal fired boilers / Oil fired boilers / Diesel motors / Petrol motors /
  Batteries；Simple reciprocating / Complex reciprocating / Steam turbines；
  Direct / Geared / Electric / Hydraulic
- Weights：Engine factor、Range、% Coal；Engine disp for machinery、Engine、
  Bunker (Max/Normal)；Load / Hull / Displacement factor

### 5.7 Performance（`06_Performance.png`）
- Stability & Seakeeping：Set Trim 滑条；Stability、Recoil、Flotation、Steadiness、
  Metacentric height、Seakeeping（左侧三格 / 右侧三格）
- Damage sustainability：Max 6.00"/152mm shell hits、Max 20"/508mm torpedo hits
- Hull & deck Room：机械/储存/分舱评语、居住与工作空间评语
- Displacement：Maximum / Normal / Standard / Light (t)、Weight/sq foot hull (lbs)
- Cost & Strength：Cost（£million）、Cross sectional strength、Longitudinal strength、
  Composite strength；评语行

---

## 6. Plimsoll 的方法与验证边界

### 6.1 参数化与剖面几何输入
项目已有 Queen Mary 的三维模型（`queen_mary_v4/*.fbx`），其船体和内部结构含工程推测，
不能称为实测型线或已验证的历史船体。Plimsoll 使用两级输入；精度需要由输入来源、
离散收敛和独立算例分别评价，不能由方法名称推出。

- **L0 参数化**（无几何）：用声明形状假设的近似公式，并标注出处与估算依赖。
- **L1 几何法**（有几何）：沿船长取站位，算每站浸没截面积 → Bonjean 曲线，
  积分得排水体积、浮心、水线面惯性矩。截面离散、纵向积分和有限包络都会影响结果。

几何法产出的量：`∇ 排水体积`、`KB 浮心高`、`Awp 水线面面积`、`I_T/I_L 惯性矩`、
`BM_T/BM_L`、`MCT1cm`、以及 **GZ 曲线**。

### 6.2 带有效性边界的 GZ 与简化破损分析
大横倾状态需要完整复原力臂与进水模型，小角度 GM 只提供局部信息。核心目标是：
- 在明确支持的角度、几何和开口状态下求载荷一致的 GZ 曲线；截断角不能冒充消失角
- 自由液面修正（FSC）——进水舱的液面效应
- 破损稳性：给定舱室进水组合 → 新浮态（吃水/纵倾/横倾）→ 剩余 GZ

1.0 通过独立数据导出契约供游戏侧读取；这里的功能目标不等于已完成 Unity 集成。

### 6.3 可脚本化
- CLI：`plimsoll compute ship.json -o result.json`
- 批量：`plimsoll sweep cases/*.json -o table.csv`
- 无 GUI 依赖，可在 CI 里跑

### 6.4 一切可溯源
每个输出字段带 `formula` 与 `source`。不确定的标 `estimate`。
公式可复算、软件可用和史实数据可信度分别验收；尚无完整的同输入软件比较，
因此不据此宣称已全面超过 SpringSharp。

---

## 7. 验证策略

三层，缺一不可：

1. **单元测试**：每个公式对照教科书手算例题（边界值、退化输入、非有限值）。
2. **靶船对照**：准备 3–5 艘史料数据完整的船（Queen Mary、Lion、Tiger、
   以及一艘同期战列舰），断言核心输出与公开数据在容差内一致。
3. **黑盒对照 SpringSharp**：同一艘船的输入，比较双方输出的关键量
   （排水量、水线面、GM、TPC）。**一致 = 互证；不一致 = 找出我们或它的系数差异，
   并把结论写成文档**。这是最有价值的一步，因为它能同时暴露双方的偏差。

容差建议：排水量 ±2%，水线面 ±5%，GM ±10%（GM 对重量分布极敏感）。
**任何超出容差的结果都必须写成文档记录，不允许悄悄放过。**

---

## 8. 分层路线

| 层 | 内容 | 依赖 | 验收 |
|---|---|---|---|
| **L0** | 静水力核心：参数化输入 → 排水量/Awp/TPC/KB/BM/GM/横摇周期；CLI + JSON | 无 | 靶船对照通过；输出可喂给 `hydrostatics.json` |
| **L1** | 几何法：站位截面积 → Bonjean → 静水力曲线；大角 GZ；自由液面修正 | L0 | GZ 曲线单调性与端点检查；与 L0 在小角度一致 |
| **L2** | 重量分组：船体/舾装/武备/装甲/动力；重心合成；舱室化 | L1 | 空船重量与公开数据对照 |
| **L3** | 破损稳性：进水组合 → 新浮态 → 剩余 GZ；对接游戏舱室模型 | L2 | 单舱/双舱进水场景可复现 |
| **L4** | 武备/装甲/动力细化；穿深与射界联动 | L2 | 与 `penetration_main.json` / `armour_zones.json` 互证 |
| **L5** | Web 界面 | L0–L4 稳定后 | — |

**先做 L0**，因为它立刻解开游戏侧 `ShipFloatPrototype` 缺来源的默认值。

---

## 9. 工程约定

- 语言：Python（核心，仅标准库 + 可选 numpy）；后续 Web 界面用 FastAPI + React。
- 目录：`tools/plimsoll/`（核心）、`tools/plimsoll/cases/`（靶船 JSON）、
  `docs/sps-reference/`（界面参考图）。
- 命名：字段名与本文 §5 一致，便于和参考界面逐项对照。
- 依赖：核心不得引入网络库；不得读环境变量以外的隐式配置。
- 每条公式在代码里以注释标注出处；无法给出出处的，函数名带 `_estimate` 后缀。

---

## 10. 待澄清（实现前必须定）

1. 排水量单位：史料常混用长吨/公吨（英国船多记长吨）。核心内部用公吨，
   输入 JSON 必须显式声明 `displacement_unit`。
2. 水线长口径：本舰 205.7 m（675 ft）vs 契约 213.4 m（700 ft）——**口径待考证**（见 §11）。
3. `Cwp` 缺来源：先用典型值 0.80，标注 estimate，待几何法（L1）算出来替换。
4. 破损稳性的舱室渗透率：游戏侧 `ShipCompartment.permeability` 是否可用于 L3。

---

## 11. 已知数据问题（来自本项目核对）

| 项 | 契约值 | 公开来源值 | 差异 |
|---|---|---|---|
| 舰长 | 213.4 m | 214.4 m（Navypedia/快懂，703.5 ft） | 1.0 m |
| 舰宽 | 27.2 m | 27.1 m（Navypedia，88'9"） | 0.1 m |
| 吃水 | 9.9 m | 8.50 m mean（Navypedia）/ 9.86 m deep（ThoughtCo） | 口径不同，非冲突 |

契约的 `213.4 m` 恰等于 MaritimeQuest 的 `700 ft`，而 Tyne Built Ships 的 `675 ft` = 205.7 m
疑似两柱间长。**建议在契约 notes 里记录这一口径存疑**，并在本工具里显式区分
`lwl / loa / lpp` 三个字段，不要再出现单一 `length_m`。
