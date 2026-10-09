# Plimsoll

> **当前计算核心（2026-10-10）**：统一项目、载荷、15 阶段协调入口、Python/CLI 与 Web 已实现。本轮独立审查的 F01–F21 已修复，核心 801 项回归与独立反例复验通过；验收、版本身份和模型边界见 [修复记录](../../docs/plimsoll-1.0/core-audit-fixes-2026-10-09.md) 与 [当前状态](../../docs/plimsoll-1.0/current-status.md)。部署状态以最新发布记录为准。
> 下文保留早期模块与算例记录，其旧测试数量和“正在整合”等措辞属于历史检查点。历史算例、软件回归和真实舰船验证分别记录。
> 核心面向船舶设计研究与方案比较；不宣称全面超越 SpringSharp 或取得工程认证。

> **2026-09-22 计算修正**：进水重心/无水 FSC 已修复；阻力警告贯穿结果与报告，缺剩余阻力时总量置空。
> 正常载荷估算与满载模型已分开，Cm/QPC/湿面积的假设显式标记。325 项回归通过、6 项变异验证通过。
> 新生成案例采用 resistance-2 / speed-power-2 schema；迁移说明与限制见
> [计算完整性修正](../../docs/sps-replacement/2026-09-22-calculation-integrity.md)。

自研舰船设计与静水力计算核心。规格见 [`docs/sps-replacement/SPEC.md`](../../docs/sps-replacement/SPEC.md)。
与 SpringSharp **无代码关系**；其界面仅作需求覆盖度检查表（参考图在 `docs/sps-reference/`）。

配对游戏：**《敌前转向》（Gefahrwend）**。
命名约定：**平台用历史意象，模块用方法命名** —— `plimsoll.hydrostatics` / `.bonjean` / `.stability` / `.damage`。

## 通用求解器（不是 Queen Mary 专用机）

**核心面向满足模型输入与适用条件的通用船型**；Queen Mary 只是随包案例，不代表支持任意几何、任意倾角或任意物理工况。SPEC §2.7 通用性契约：

- 核心模块**零船只常量、零仓库路径** —— `tests/test_generic_ship.py` 源码扫描把守（变异验证过）；
- 每艘船 = 一组案例 JSON（`plimsoll-ship-1` / `-weights-1` / `-armour-1` / `-guns-1`），
  型线用 `plimsoll-offsets-1` JSON 随案例携带（`hull.offsets_path` 或 CLI `--offsets`）；
- 通用 CLI 用法（任何船）：
  ```bash
  python cli.py <你的船>.json              # L0 表
  python cli.py <你的船>.json --gz         # + GZ（需案例声明 offsets_path 或 --offsets）
  python cli.py <你的船>.json --gz --offsets 船型线.json --deck-z 8.2
  ```
- 通用性活证据：`cases/generic_test_steamer_1910.json`（90 m 货船，解析锚定全链路）；
- `tools/gen_*.py` 是本项目数据的适配器，不属于核心 —— 给别的船配数据时照抄其结构即可。

## 已有基础模块（不代表 1.0 已验收）

### L0 · 参数化静水力（`hydrostatics.py`）
只有长宽吃水与系数时用。一参数水线面模型 `f(x) = (1−(2x/L)²)^p`，各阶矩用 Γ 函数**解析**求出，
给定 `Cwp` 反解 `p` 后其余量唯一确定 —— 没有"再挑几个系数"的自由度。
`p → 0` 退化为方箱，此时 `KB=T/2`、`BM_T=B²/(12T)`、`I_L=B·L³/12`，单测直接断言这组闭式解。

### L1 · 几何法静水力与大角稳性（`geometry.py` + `geometric.py`）
有站位剖面时用。几何能力取决于输入型线的质量；由估算模型生成型线，并不意味着知道真实舰船的水下形状。

- **真实积分**：逐站把剖面多边形按水线切，算面积与一阶矩，再沿 x 积分得 ∇、浮心
- **Bonjean 曲线**：站剖面面积 vs 水线高
- **大角稳性 GZ**：**等体积倾斜** —— 每个横倾角下重解平衡水线，再按
  `GZ = y_B·cosφ + (z_B − KG)·sinφ` 求复原力臂
- **纵倾平衡（2.2）**：`geometric.solve_trim_equilibrium(hull, target_volume, target_lcb)`
  给定排水体积与浮心纵向位置（= LCG），嵌套求根解出水线截距 d 与纵倾角 θ
  （θ > 0 = 艏倾）；体积与 LCB 同时达标，否则抛错
  。注意该旧接口使用 `LCB=LCG` 近似；新的加载求解器已核验倾斜后的完整力矩，见 [求解器契约](../../docs/plimsoll-1.0/stability-api.md) 与 [解析验算](../../docs/plimsoll-1.0/equilibrium-validation-design.md)。统一计算入口仍在整合。
- **自由液面 FSC（阶段 3）**：`freesurface.free_surface_correction` /
  `geometric.gz_curve(..., free_surface_tanks=)` —— 矩形舱 `i=L·b³/12`，
  `KG_eff=KG+FSC`；空/满舱不计

```bash
PY="C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe"

"$PY" tools/plimsoll/cli.py tools/plimsoll/cases/queen_mary_1913.json \
        --gz -o tools/plimsoll/cases/queen_mary_1913.result.json
"$PY" tools/plimsoll/cli.py --selftest
"$PY" tools/plimsoll/tests/test_hydrostatics.py        # L0：28 项
"$PY" tools/plimsoll/tests/test_geometric.py           # L1：35 项
"$PY" tools/plimsoll/tests/test_offsets_import.py      # 型值表：16 项
"$PY" tools/plimsoll/tests/test_trim_equilibrium.py    # 纵倾平衡 2.2
"$PY" tools/plimsoll/tests/test_freesurface.py         # 阶段 3 FSC
"$PY" tools/plimsoll/tests/test_flood_combination.py   # 阶段 4.1 进水组合
```

## Queen Mary 案例结果

| 量 | L0 参数化 | L1 几何法 | 说明 |
|---|---:|---:|---|
> **以下为 2026-09-21 修正 LWL 后的结果**（LWL 205.7 → 212.8 m，Cb 0.551 → 0.533；
> 两者必须同步改，否则排水量虚高 3.4% —— 详见「已知未决」第 2 条）。

| 量 | L0 参数化 | L1 几何法 | 说明 |
|---|---:|---:|---|
| 排水体积 m³ | 26127 | 26095 | 差 0.12% |
| 水线面 m² | 4613.5 | 4628.4 | 差 0.32% |
| BM_T m | 7.946 | 7.950 | 差 0.04% |
| **KB m** | **5.132** | **5.035** | **差 −1.88%，见下** |
| KM m | 13.078 | 12.985 | 差 −0.71% |

此表记录早期参数化参考船型的两法差异，不是 Queen Mary 实测浮心的误差结论。L0 用 Morrish 近似，L1 用离散几何积分；差异还需结合几何分辨率和共同输入核对。旧测试区间是回归约束，不能替代独立基准与收敛验证。

GZ 曲线（KG = 8.6 m 为 estimate，甲板按 1.6T 假定）：

| 横倾 | 5° | 10° | 15° | 20° | 30° | 40° | 50° | 60° |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GZ m | 0.356 | 0.668 | 0.949 | 1.210 | **1.557** | 1.505 | 1.213 | 0.781 |

最大复原力臂 **1.557 m @ 30°**，60° 仍为正。**甲板浸没角约 20.6°** ——
超过它，GZ 就取决于假定的甲板高度与舷侧形状（参照船体此处是合成的，不是本舰真实型线）。

## 按纪律写死的几条

- 核心**纯函数**：`dict → dict`，不 import GUI / Unity / 网络库。
- 核心**不做四舍五入**：全精度 float，取整只发生在 CLI 显示层。
- 每个输出项都有 `formula` / `source` / `estimate`；测试断言 trace 覆盖全部值且都有来源。
- 站位间距默认 **cosine**：船体两端剖面面积按 `s^p`（p<1）衰减，端部斜率趋于无穷，
  均匀站位下梯形积分收敛极慢（实测 161 站仍有 −0.38% 体积误差）。
- 剖面多边形默认 96 边：24 边会系统性低估面积（`z^0.452` 是凹曲线），误差 0.32% → 96 边降到 0.05%。

## 验证方式（三层）

1. **解析解**：方箱。静水力逐位吻合（体积/KB/BM_T/I_T 到 1e-6）；
   GZ 与闭式解 `GM·sinφ + (B²/24T)·sin³φ/cos²φ` 吻合到 1e-6。
   ⚠️ 注意：常见写法 `BM·sinφ·cosφ + (T/2−KG)·sinφ` 是**错的**（它假设 `y_B = BM·sinφ`，
   而实际 `y_B = BM·tanφ`），本模块用的是正确形式。
2. **L0 ↔ L1 交叉验证**：同一形状假设下两条独立路径必须一致（水线面派生量差 <0.1%）。
3. **数值性质**：离散收敛性、单峰性、等体积守恒、初始斜率 = GM（0.01° 处逐位吻合）。

## 已知未决（诚实清单）

| 项 | 状态 |
|---|---|
| `waterplane_coeff = 0.80` | **estimate**，待 L1 从真实船体算出后替换 |
| `kg_m = 8.6` | **estimate**，KG 属 L2 重量分组；GM 与之强耦合，故输出附 KG 敏感性表 |
| 参照船体 | `make_reference_hull` 是**合成**船体（与 L0 同源，用于交叉验证），**不是 Queen Mary 真实型线** |
| 真实型线 | 待从 `queen_mary_v4` 的 FBX/blend 抽取站位剖面（下一步） |
| 甲板以上形状 | 合成船体用直壁，故 >20.6° 的 GZ 不具代表性 |
| 纵倾平衡 | **已实现（2.2）**：`solve_trim_equilibrium` 给定 V 与 LCB(=LCG) 解 `(d, θ)`；`target_lcb` 必须与 `xlcb` 同坐标原点 |
| 大纵倾 LWL 耦合 | **未做**（阶段 2.3）：大 θ 下水线长变化对排水量的影响尚未专项交代 |
| 自由液面 FSC | **已实现（3.1/3.2）**：`freesurface.py` + `gz_curve(free_surface_tanks=)`；舱室须显式 L×b，游戏侧 compartment JSON 无此字段 |
| 进水组合 | **已实现（4.1）**：`damage.flood_combination` |
| 破损浮态/剩余 GZ/场景 | **本分支 damage-loop**：`solve_flooded_equilibrium` / `remaining_gz_curve` / `run_damage_scenarios.py` |
| 一键回归 | `tools/plimsoll/run_all_tests.py` |
| L1 trace | `integrate()["trace"]` 含 formula/source |
| 水线长口径 | **已解决**：LWL = 212.8 m（698 ft，worldwar1.co.uk 明写 "698 feet waterline"），LOA = 214.4 m。契约的 213.4 介于两者，最可能是维基「Length」字段口径。模型全长 213.4 与 LWL 212.8 差 0.3% |
| 吨位单位 | 史料常混用长吨/公吨，核心内部按公吨 |

## L1 · 真实型线接入（`offsets.py`）

`hull_offsets.json` 是本项目**约定的真实型线接入点**（`queen_mary_v4.py:63-64`）。
本模块既读那个文件，也能直接从生成脚本里取出内建型值表（用 `ast` 静态解析，不 import —— 那个脚本要 bpy）。

**当前的型线是估算的，不是史实。** 生成脚本注释原话：「三个主尺度是给定的，
**之间的形状是估算**」，`make_hull` 亦标注 `estimated until a lines plan is supplied`。
全仓搜索确认不存在 `hull_offsets.json`。所以 Plimsoll 现在吃的是这张估算表 ——
**来源标 `builtin_estimate`，不能当史实**。

坐标映射：`x_plimsoll = y_blender`，`y_plimsoll = x_blender`，`z_plimsoll = z_blender`，
**无旋转无镜像**。注意**不要读 FBX**（导出时绕 Z 转了 180°，`EXPORT_YAW_DEG=180`）。

### 型值表船体的结果（设计水线 z = 0）

| 量 | Plimsoll | 仓库既有记录 | 差 |
|---|---:|---:|---:|
| 浸没体积 m³ | 30,943.9 | 30,663.7 | +0.91% |
| 水线面 m² | 4,628.4 | 4,610.4 | +0.39% |
| **VCB（相对水线）m** | **−3.895** | **−3.89** | **+0.13%** |
| KB m | 6.005 | — | |
| BM_T m | 7.272 | — | |
| KM m | 13.277 | — | |
| **GM @ KG=8.6 m** | **4.677** | — | |

GZ 曲线（KG = 8.6 m）：10° 0.805 · 20° 1.559 · 30° 2.063 · **40° 2.116（峰值）** · 50° 1.916。

### ⚠️ 两个必须跟着结论一起说的限制

1. **甲板浸没角约 20.6°。** 干舷 5.10 m、半宽 13.6 m，`atan(5.10/13.6) = 20.6°`。
   本模型船体只到主甲板（z = 5.10），超过该角后浸没剖面被截断，GZ 偏小。
   对完整船而言这也正是"稳性范围"的边界，所以 **20.6° 以上的数值不应当引用**。
2. **型线本身是估算的**（生成脚本自述）。

   ⚠️ **此处修正过一处我自己的错误。** 早先我把 LWL 取成 205.7 m（Tyne Built Ships 的 675 ft），
   并据此断言"模型比实船偏长 3.7%"——**两个都错**。多源核对后：

   | 来源 | 舰长 |
   |---|---|
   | 维基（Infobox） | **700 ft 1 in = 213.4 m** |
   | Navypedia | 214.4 m |
   | MaritimeQuest | 700 ft |
   | ThoughtCo / 快懂百科 | 703 ft 6 in = 214.4 m |
   | Tyne Built Ships | **675.0 ft = 205.7 m** ← **孤例，我不该用它** |

   五源聚在 213.4–214.4 m，模型（全长 213.4 m）与实船总长 214.4 m 只差 **0.5%**。
   另外维基这组数正是本项目契约的 `length_m=213.4 / beam_m=27.2 / draft_m=9.9`
   —— 契约的来源清楚了，量级也是对的。

   **已处理**：`cases/queen_mary_1913.json` 的 `lwl_m` 已改为 **212.8**，
   `block_coeff` 同步改为 **0.533**。

   ⚠️ **这两个量必须一起改**：`Cb` 原本是从错误的 LWL 反推的（0.551 = 26770 ÷ (205.7×27.1×8.5×1.025)），
   构成循环论证 —— 只改 LWL 不改 Cb，排水量会虚高 **3.4%**。改后偏差回到 **+0.04%**。

   **一个意外的正面结果**：改对 LWL 后，L0 参数化的水线面从 4459.6 变为 **4613.5 m²**，
   与项目现有常数 **4610.4 只差 0.07%**（此前差 3.3%）。
   即：**那个常数一直是对的，之前的偏差全来自我用错的 LWL。**

### 一个重要佐证：模型的体积特性与实船吻合（2026-09-21 新增）

此前我把"型线是估算的"说得过重了。准确的说法是：**形状细节是估算，但积分出来的体积特性对得上实船。**

把型值表船体在**自身设计水线 z = 0**（龙骨 −9.9 m → 吃水 **9.9 m**，正是实船满载吃水）上积分：

| | 值 |
|---|---:|
| 模型浸没体积 | 30,943.9 m³ |
| 模型排水量（×1.025） | **31,717 t** |
| 实船满载（Navypedia / Tyne） | 31,650 t → 差 **+0.21%** |
| 实船满载（worldwar1.co.uk） | 31,486 t → 差 +0.73% |
| **模型 Cb（213.4/9.9）** | **0.5405** |
| **实船满载 Cb（反解 212.8/9.9）** | **0.5408** → 差 **0.06%** |

另一处一致性：型值表隐含的水线面系数 = 4610.4 ÷ (212.8 × 27.1) = **0.7994**，
与 L0 假定的 `Cwp = 0.80` 吻合到 0.08%。

**但这条佐证有边界，不要越用**：它只验证了**体积与方形系数**。
两艘体积完全相同、Cb 相同的船，可以有完全不同的 KB / BM / GZ ——
**形状分布未经外部验证**，这仍是型线图才能定论的事。

### 一个尚未查明的差异（如实记录）

闭合体积（龙骨→主甲板）本方法给 **55,234 m³**，其多面体精确值 **54,226 m³**，
而 v3 FBX 的 `hull_signed_volume_m3` 为 **54,865.7 m³** —— 三者不完全一致。
已排除：剖面采样密度（33 点 vs 96 点结果相同）、站位间距（61→481 站不再收敛）、
插值复现（表结点插值逐位通过）。**原因未查明**，故测试只断言量级与正负，不假装精确。
注意该项在水线以上，不影响浮态计算。

## 与项目现有资产的关系（此处修正过一处早先的说法）

游戏侧 `ShipFloatPrototype.cs` 用 `waterplaneAreaM2 = 4610.4`。
我早先说它「无来源」——**不准确，现已查明来历**：

> **4610.4 等于「对 22 个型值表结点直接做梯形积分」，可逐位复现（0.000%）。**

而网格实际使用的是 `station_params` 的三次插值曲线，其水线面为 **4,628.9 m²**。
也就是说：**这个数来自比几何更粗的求积，比模型自身几何低约 0.4%**；
浸没体积同理偏低约 0.9%（30,663.7 vs 30,943.9）。

`TestAnchorProvenance` 把这套来历固化成了测试 —— 包括「表结点梯形积分再现锚点」
和「我们的提取必须对齐插值曲线、而不是迁就那个粗求积的锚点」两条断言。
**是否把游戏里的 4610.4 更新为网格精确值，是个待你决定的动作。**
