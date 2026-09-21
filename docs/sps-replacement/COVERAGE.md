# 覆盖度检查表 · Plimsoll vs SpringSharp · 2026-09-21

> **这就是 `SPEC.md` §5 承诺但从未创建的那份表。**
> 维护纪律：**新增能力先在这里改状态，再写代码**；砍掉能力要留理由。
>
> 基准一：`docs/sps-reference/` 七张界面图（字段经逐图清点，2026-09-21，含对 SPEC §5 的七处纠正）。
> 基准二：`SPEC.md` §5 字段清单与 §8 分层路线。
>
> 图例：**✅** 已实现且有测试 · **◐** 部分 · **○** 未实现、已计划 · **✖** 明确不做（写理由）· **—** 参考材料未捕获

---

## 1. 页级总览（这张表回答"还原到位没有"）

| SPS 页签 | 图上字段数 | 状态 | Plimsoll 对应物 | 缺口性质 |
|---|---:|:---:|---|---|
| **Hull** | 33 | **◐** | `hydrostatics.py`(L0) + `offsets/geometry/geometric`(L1) | 模型有；少湿面积/自然航速等派生显示 |
| **Freeboard** | 26 | **✖→○** | 无（仅 CLI 有甲板浸没角告警） | 模型缺；甲板分段数据缺 |
| **Guns** | 23 | **◐**（模块已建） | `guns.py` v0（Weights 表 + 齐射 + Magazine） | 文献值已采集（NavWeaps 等）；**Armour 行缺**（炮塔装甲）；副炮装药缺 |
| **Weapons** | 27 | **○** | 无 | 数据缺（鱼雷/水雷/深弹） |
| **Armour** | 28 | **◐**（模块已建） | `armour.py` v0（重量表 + SPS 视图） | 厚度带来源已有；**炮塔装甲未计入**（manifest 无选面 role）；面积全 estimate |
| **Engines** | 27 | **✖→○** | 无 | **全无数据**（无功率/锅炉/燃料） |
| **Performance** | 25 | **◐** | 稳性部分即我们的差异化 | GM/GZ/破损已强；Seakeeping/成本/强度 ✖ |
| **（SPS 没有的）静水力曲线 / GZ / FSC / 破损稳性** | — | **✅** | 全部 | **我们的差异化，已完成 129 项测试** |

**公共部分（对标 SPS）覆盖率 ≈ 13%——只有 Hull 的一半多一点。**
**差异化部分（SPS 做不到的）≈ 100% 完成。**
即：**我们把"纵深"做满了，"宽度"还是一片空地。**

**层路线对照（SPEC §8）**：L0 ✅ → L1 ✅ → **L2 ❌（被降级到"阶段 7.2"，KG 只能手填）** → L3 ✅（部分）→ L4 ❌ → L5(Web) **曾提前开工、现已叫停**。

---

## 2. 逐页字段对照

### 2.1 Hull（33 项）——唯一动工的一页

| 字段（原图） | SPS | Plimsoll | 证据 / 说明 |
|---|:---:|:---:|---|
| Name / Country / Type / Year | 输入 | ✅ | 案例字段 pass-through |
| Ship laid down / Engine built | 输入 | ◐ | `dates.laid_down` 有；Engine built 无 |
| 单位下拉（feet/metres） | 输入 | ✖ | **明确不做**：内部一律 SI，界面层换算（SPEC §3.1） |
| Length Waterline / Overall | 输入 | ✅ | `lwl_m` 212.8（六源核对）`loa_m` 214.4；`lpp_m` 待拆（PLAN 1.3）|
| Beam Hull | 输入 | ✅ | 27.1 |
| Beam Bulges | 输入 | ✖ | **明确不做**：防雷鼓包，本舰无 |
| Draught (hull only) Normal / Max | 输入 | ✅ | `draught_normal_m` 8.5 / `draught_deep_m` 9.9 |
| 船型滑条（Destroyer↔Merchant） | 输入 | ✖ | **明确不做**：直接输入 Cb/Cwp 更诚实；滑条会把形状假设藏进 UX |
| Block Coeff 刻度盘 + Normal/Max | 输入 | ✅ | `block_coeff` 0.533（反推自排水量，带来源）|
| Displacement Normal / Max | 输入 | ◐ | 输入接受且做一致性检查（±5% 告警）；"Max" 口径未进计算 |
| Normal / Max volume | 输出 | ✅ | L0 `∇=L·B·T·Cb`；L1 逐站积分 |
| **Waterplane area** | 输出 | ✅ | L0 `Cwp·L·B`=4613.5；L1 积分=4610.4（差 0.07%）|
| **Wetted surface area** | 输出 | **✖** | 未实现。 型值表可积 girth，**列入待办** |
| **Length:Beam** | 输出 | **✖** | 未实现（平凡，顺手可补） |
| **Natural Speed** | 输出 | **✖** | 未实现（`1.09·√L` 系经验式，须带出处再上） |

### 2.2 Freeboard（26 项）——未动工

甲板分段（Forecastle/Fore/Aft/Quarter deck 的 %Lwl）、艏艉干舷（各 4 行）、
甲板型（Flush/Mid break）、船首型/船艉型、Ram Length、Stern overhang、Depth Unlocked、
Sheer 示意图、**Average freeboard（输出）**。

→ **全未实现。** 可从型值表+甲板高推出 Average freeboard 与浸没角（CLI 已有 20.6° 告警雏形）。
**拦路石**：甲板分段比例是纯设计输入，本舰无来源 → 标 estimate 或先不做。

### 2.3 Guns（23 项）——模块已建（v0）

- Weights 表（行：Guns/Mounts/Armour/Total/Broadside lbs/Broadside kg/Magazine；
  列：Main/2nd–5th/Total）—— **Summary 全是输出**，输入在 Battery 子页。
- **已具备**：主炮口径 343 mm、倍径 45、弹重 1400 lb、射距-穿深曲线（`penetration_main.json`，带源）；
  数量 8 管/4 塔/16 门副炮（`ship_contract.json`）。
- **【2026-09-22 已建】`guns.py` v0 + `tools/gen_guns_case.py`**：Weights 表全行输出。
  外部数据已采集（NavWeaps/维基/Jutland 名录）：主炮 76.102 t/门、BII 座 600 t
  （BII* 未单列 → estimate）、装药 297 lb、设计储弹 80 发/门；副炮 2.134 t/门、弹 31 lb、150 发/门。
  齐射：主炮单舷 8 门 = 11,200 lb / 5,080 kg；主炮 Magazine（as-built）= 492.6 t。
  **仍未覆盖**：Armour 行（炮塔装甲重，与 Armour 页同缺口）；副炮装药（Magazine 偏低）；
  Battery 子页的每门炮细目（炮架/座圈/锁定，需 SpringSharp3b3 截图或外部采集）；
  弹药库容量换算、射速输出。口径矛盾（设计 80 / 战时 110 发/门 vs 名录 661 t）已记录于案例 `_note`。

### 2.4 Weapons（27 项）——未动工

鱼雷（主/副：数量/直径/长/布置）、水雷、深弹、**Misc weight 五分区**
（Hull-Below/Above water、On deck、Above Deck、Void）。
→ **全未实现。** Misc weight 分区其实是 **L2 的输入格式**，应并入 L2 设计。

### 2.5 Armour（28 项）——数据半齐，模块未建

- Belts & Bulkheads 表：**Length/Height 是用户输入，Weight 是输出**（图上证实）。
- **已具备**：14 个分区的厚度，**逐区带来源**（wiki 9in KC 主带 / 6in 上带 / 4in taper / 2.5in 甲板 /
  1in 下甲板 / 4in 舱壁 / 9in 炮座 / 10in 司令塔…，`armour_zones.json`）。
- **缺**：各区**长/高/面积**。实测从 `object_manifest.json` 的 101 个对象包围盒按 role 选面可推，
  **估算合计 6,821 t = 排水量 25.5%**，正落史实区间（狮级 6,000–7,000 t / 22–25%）。
  ⚠️ 必须 estimate 标注：包围盒无朝向信息，曲面展开面积取曲率系数 1.10，炮管不计入装甲。

### 2.6 Engines（27 项）——未动工，**数据完全空白**

Max/Cruise speed、轴数、Friction/Wave resistance、Power (hp/kW)（全输出）、
锅炉/主机型式复选框、Range、%Coal、Engine factor（输入）、
Engine weight / Bunker / Displacement factor（输出）。
→ **仓库里没有任何功率/锅炉/燃料数据**（只有 `speed_knots: 28.0`）。**需外部采集**。

### 2.7 Performance（25 项）——差异化的主战场

| 字段 | SPS | Plimsoll |
|---|:---:|---|
| Stability / Recoil / Flotation / Steadiness / Seakeeping | 输出（**数字**，非评语） | ◐ GM/横摇周期 ✅；**Seakeeping ✖** |
| Set Trim 滑条 | 输入 | ✅ `solve_trim_equilibrium`（比 SPS 强：真解平衡） |
| **Damage sustainability**（Max shell/torpedo hits） | 输出 | ◐ 我们有**真破损稳性**（进水→新浮态→剩余 GZ），比 SPS 的"允许几发"更深 |
| Hull & deck Room（机械/储存/居住评语） | 输出 | ✖ |
| Displacement Max/Normal/Standard/Light | 输出 | ◐ Normal/Deep 有；**Standard/Light 无** |
| **Cost (£million)** | 输出 | **✖** |
| Cross-sectional / Longitudinal / Composite strength | 输出 | **✖**（纵强度与 L2/L4 相关） |

---

## 3. 参考材料的三个洞（实现前必须补）

1. **Guns 的 Battery 子页截图从未捕获**——而那里才是全部输入（每门炮重/座圈/弹药/锁定）。
   现有 `02_Guns.png` 只有 Summary 输出页。**要么跑本地 `SpringSharp3b3.exe` 补截图，要么靠外部数据源**。
2. 七处 SPEC §5 的笔误/遗漏已按图纠正（如 Hull 页输出还含 Normal/Max volume；
   Weapons 页的 Misc weight 五分区；Armour 页 Length/Height 是输入）。
3. 要做**黑盒对照**（SPEC §7.3，"最有价值的一步"），本地 `SpringSharp3b3/` 就有可执行文件，
   且这台机器上跑过（工作区有截图）。**纯人肉字段清单有上限，跑起来才有权威对照。**

---

## 4. 结论与顺序

1. **"还原到位没有"的答案：没有。** SPS 公共部分 ~13%，六页未动工；
   但差异化（静水力/GZ/FSC/破损）100%。
2. **先补 L2（重量分组）**——它是 Guns/Armour/Weapons 三页的共同前置，
   也是 GM 从"手填 KG"变"分组合成"的唯一路径。素材审计结论：**缺模型不缺关键数据**
   （装甲：厚度有源+面积可推；炮：弹重有；动力：全缺，先 estimate 占位）。
3. L2 之后再补各页，顺序按"数据齐不齐"：**Armour（数据半齐）→ Guns（弹重有）→
   Hull 补齐（湿面积/自然航速）→ Freeboard → Weapons → Engines（需采集数据）**。
4. **网站继续搁置**，直到覆盖度检查表上六页至少到 ◐。
