# 覆盖度检查表 · Plimsoll 与 SpringSharp · 2026-09-22

> 本表保留七页参考字段的盘点；功能状态只能在实现和验证后更新。
> 1.0 的范围与验收以 [批准目标](../plimsoll-1.0/spec.md) 为准，执行状态见 [当前状态](../plimsoll-1.0/current-status.md)。
> 不以字段数量、单元测试数量推算产品完成百分比；未做同输入基准比较，不宣称全面超越 SpringSharp。
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
| **Freeboard** | 26 | **◐**（模块已建） | `freeboard.py` v0（加权平均干舷 + 浸没角） | **无外部文献源**：型深/干舷全由模型包围盒推得（estimate）；sheer/细分段缺 |
| **Guns** | 23 | **◐**（模块已建） | `guns.py` v0（Weights 表 + 齐射 + Magazine） | 文献值已采集（NavWeaps 等）；**Armour 行缺**（炮塔装甲）；副炮装药缺 |
| **Weapons** | 27 | **◐**（模块已建） | `weapons.py` v0（鱼雷 + 水雷/深弹 + Misc 五分区） | 鱼雷有源；**单雷全重/雷长缺**；水雷深弹与 Misc 五分区无数据 |
| **Armour** | 28 | **◐**（模块已建） | `armour.py` v0（重量表 + SPS 视图） | 厚度带来源已有；**炮塔装甲未计入**（manifest 无选面 role）；面积全 estimate |
| **Engines** | 27 | **◐** | `engines.py` + `resistance.py` | Taylor 估算已有；同载荷闭环、Holtrop 对照及主机重量仍待完成 |
| **Performance** | 25 | **◐** | 稳性部分即我们的差异化 | GM/GZ/破损已强；Seakeeping/成本/强度 ✖ |
| **静水力曲线 / GZ / FSC / 破损稳性** | — | **◐** | `geometric.py` / `damage.py` | 基础算法有测试；完整重量驱动、倾斜液体、连通进水时间线和有效性边界尚未全部实现 |

**撤销旧“公共部分 13% / 差异化 100%”表述。** 当时没有稳定的计分分母，且与随后新增的模块矛盾。已有函数、完整数据、可操作界面、物理有效性和产品验收必须分别核对。

**层路线现状**：L0/L1 有基础实现；L2 仅装甲重量案例和 KG 合成，三轴全船载荷待补；L3 有简化破损计算，完整闭环待补；本地 Web 已获 1.0 目标授权，在核心接口稳定后继续。

---

## 2. 逐页字段对照

### 2.1 Hull（33 项）——参数与型线基础已实现

| 字段（原图） | SPS | Plimsoll | 证据 / 说明 |
|---|:---:|:---:|---|
| Name / Country / Type / Year | 输入 | ✅ | 案例字段 pass-through |
| Ship laid down / Engine built | 输入 | ◐ | `dates.laid_down` 有；Engine built 无 |
| 单位下拉（feet/metres） | 输入 | ○ | 内部 canonical SI；1.0 统一显式单位换算，界面展示必须标单位 |
| Length Waterline / Overall | 输入 | ✅ | `lwl_m` 212.8（六源核对）`loa_m` 214.4；**LWL 另有型线实算口径** `hull.waterline_length()`：QM 型线 z=0（满载吃水）得 213.4 m > 正常吃水 212.8（方向自洽）；`lpp_m` 无源 → 仍缺 |
| Beam Hull | 输入 | ✅ | 27.1 |
| Beam Bulges | 输入 | ✖ | **明确不做**：防雷鼓包，本舰无 |
| Draught (hull only) Normal / Max | 输入 | ✅ | `draught_normal_m` 8.5 / `draught_deep_m` 9.9 |
| 船型滑条（Destroyer↔Merchant） | 输入 | ✖ | **明确不做**：直接输入 Cb/Cwp 更诚实；滑条会把形状假设藏进 UX |
| Block Coeff 刻度盘 + Normal/Max | 输入 | ✅ | `block_coeff` 0.533（反推自排水量，带来源）|
| Displacement Normal / Max | 输入 | ◐ | 输入接受且做一致性检查（±5% 告警）；"Max" 口径未进计算 |
| Normal / Max volume | 输出 | ✅ | L0 `∇=L·B·T·Cb`；L1 逐站积分 |
| **Waterplane area** | 输出 | ✅ | L0 `Cwp·L·B`=4613.5；L1 积分=4610.4（差 0.07%）|
| **Wetted surface area** | 输出 | **◐→✅** | `hull.py`：Mumford 经验式（L0）+ 逐站湿周长积分（L1）。正常载荷经验式 6147.6 / 满载模型积分 6407.9 m²；工况不同，不作两法互证 |
| **Length:Beam** | 输出 | **✅** | `hull.form_ratios()`，定义式（QM 7.852） |
| **Natural Speed** | 输出 | **◐→✅** | `hull.natural_speed()`：**两口径并列** —— Froude 兴波速度（有源，35.43 kn）+ SPS 惯例 1.09·√L_ft（**estimate，常数无公开出处**，28.8 kn），并给出 Fn=0.324 |

### 2.2 Freeboard（26 项）——模块已建（v0），但**数据是本页最大的缺口**

甲板分段（Forecastle/Fore/Aft/Quarter deck 的 %Lwl）、艏艉干舷（各 4 行）、
甲板型（Flush/Mid break）、船首型/船艉型、Ram Length、Stern overhang、Depth Unlocked、
Sheer 示意图、**Average freeboard（输出）**。

**【2026-09-22 已建】`freeboard.py` v0 + `tools/gen_freeboard_case.py`**：
- 加权平均干舷 `f̄ = Σ(L段·f段)/ΣL段`（段内艏艉线性取均值）+ 逐段长度（%Lwl → m）。
- **干舷↔稳性的桥**：每段输出 `deck_immersion_deg = atan(f段/(B/2))` —— 与 cli.py 的
  GZ 甲板浸没告警同一判据；低于 15° 会警告「GZ 在该角以上不可信」。
- QM 数据**全部由模型推得（无外部文献源）**：型深 = Hull z[−9.90, 5.10] = 15.0 m →
  主甲板干舷 6.5 m（正常吃水）；Forecastle 段 58.4% / 8.90 m / 浸没角 33.3°，
  Quarterdeck 段 41.6% / 7.12 m / 27.7°；加权平均干舷 8.16 m。**全标 estimate**。
- **仍缺**：Fore/Aft 细分段、真实舷弧（sheer，模型是平的）、甲板型、船首/船艉型、
  Ram length、Stern overhang —— 均为纯设计输入，本模块不做（同 Hull 页滑条原则）。

上述基础输出已实现；真实舷弧与分段仍缺数据，现有模型推导必须保留 estimate。甲板浸没提示不等于已验证的开口进水角。

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

### 2.4 Weapons（27 项）——模块已建（v0），鱼雷部分有源

鱼雷（主/副：数量/直径/长/布置）、水雷、深弹、**Misc weight 五分区**
（Hull-Below/Above water、On deck、Above Deck、Void）。

**【2026-09-22 已建】`weapons.py` v0 + `tools/gen_weapons_case.py`**：
- 鱼雷：管数/携带数/直径/布置 pass-through，**战斗部装药总重 = 携带数 × 单雷装药**；
  **单雷全重未采集 → 置 None（不能用装药重冒充，差一个数量级）**，雷长同样缺。
  QM：2 × 533 mm 水下舷侧管、14 枚 Mk II***、战斗部 400 lb (181 kg) → 装药总重 **2.534 t**。
- 水雷/深弹：**没给 = 没数据（None，带警告）**，显式给 0 才是"确实不装备"——
  QM 两项均无文献源，置空。
- Misc weight 五分区：小计 + 占排水量比例（>25% 告警，防与船体钢料重复计入）+ **L2 接口警告**
  （分区只有重量、没有 kg_m，不能直接喂 `weights.py` 合成 KG）。QM 五分区全无数据。
- 来源冲突已记录：战斗部 400 lb（维基）vs 515 lb（MaritimeQuest）；射程 10,000 yd @ 29 kn
  （维基）vs 10,750 yd @ 31 kn（MaritimeQuest）。

### 2.5 Armour（28 项）——基础模块已有，完整重量对接待补

- Belts & Bulkheads 表：**Length/Height 是用户输入，Weight 是输出**（图上证实）。
- **已具备**：14 个分区的厚度，**逐区带来源**（wiki 9in KC 主带 / 6in 上带 / 4in taper / 2.5in 甲板 /
  1in 下甲板 / 4in 舱壁 / 9in 炮座 / 10in 司令塔…，`armour_zones.json`）。
- **缺**：各区**长/高/面积**。实测从 `object_manifest.json` 的 101 个对象包围盒按 role 选面可推，
  **旧案例估算合计约 6,821 t，占其参考排水量约 25.5%**；比例接近某个经验范围不能验证选面、装甲面积或历史质量正确。
  ⚠️ 必须 estimate 标注：包围盒无朝向信息，曲面展开面积取曲率系数 1.10，炮管不计入装甲。

### 2.6 Engines（27 项）——模块已建（v0，只做有源部分）

Max/Cruise speed、轴数、Friction/Wave resistance、Power (hp/kW)（全输出）、
锅炉/主机型式复选框、Range、%Coal、Engine factor（输入）、
Engine weight / Bunker / Displacement factor（输出）。

**【2026-09-22 已建】`engines.py` v0 + `tools/gen_engines_case.py`**：
- **有源就给**：轴数 4、4 × Parsons 直驱蒸汽轮机、42 × Yarrow 锅炉、
  设计 75,000 shp = **55,927.5 kW**（旧模块使用 1 shp ≈ 745.7 W 的舍入常数）、试航 83,000 shp = 61,893.1 kW、
  最大 27.5 kn（试航 28.1 kn @ 83,000 shp）、Bunker 4,770 t（煤 3,600 + 油 1,170，**%Coal 75.47%**）、
  续航 5,610 nm @ 10 kn。
- **量级校核（estimate）**：海军部系数 `C = Δ^(2/3)·V³ / P` = **248**（军舰常见 200–300，
  说明功率/航速/排水量自洽）+ 最大航速 Froude 数。
- **尚需完成/核对**：Taylor 阻力已经独立实现，Holtrop 对照纳入 1.0；Engine weight 将按明确来源或带区间的工程估算进入重量体系。Displacement factor / Engine factor 的 SPS 自有口径未证实，不能伪造同名等价值。旧 `sps_view()` 的未实现标签也须在集成阶段按实际能力更新。
- 巡航速度无来源 → 置空（不是 0）。

### 2.7 Performance（25 项）——差异化的主战场

| 字段 | SPS | Plimsoll |
|---|:---:|---|
| Stability / Recoil / Flotation / Steadiness / Seakeeping | 输出（**数字**，非评语） | ◐ GM/横摇周期 ✅；**Seakeeping ✖** |
| Set Trim 滑条 | 输入 | ◐ 已有 `solve_trim_equilibrium`；全船三轴载荷联动尚待验收，不据函数名宣称优于 SPS |
| **Damage sustainability**（Max shell/torpedo hits） | 输出 | ◐ 采用显式进水与剩余稳性的另一种建模范围；它不等价于命中次数估计，且完整时间线与液体几何待完成 |
| Hull & deck Room（机械/储存/居住评语） | 输出 | ✖ |
| Displacement Max/Normal/Standard/Light | 输出 | ◐ Normal/Deep 有；**Standard/Light 无** |
| **Cost (£million)** | 输出 | **✖** |
| Cross-sectional / Longitudinal / Composite strength | 输出 | **✖**（纵强度与 L2/L4 相关） |

---

## 附：7.3 方法选择记录（2026-09-22）

| | Taylor-Gertler | Holtrop-Mennen |
|---|---|---|
| 方法与资料 | Taylor 标准系列；具体图谱版本和归一化仍需逐页核对 | 1982 扩展包含细长军舰研究，不能概括为仅限民船 |
| 分解 | Froude：摩擦（Schoenherr + 0.4e-3）+ 剩余阻力图谱 | 回归闭式 `Rt=Rf(1+k1)+Rapp+Rw+Rb+Rtr+RA` |
| 摩擦线 | Schoenherr | ITTC-1957 |
| 偏差判断 | 旧“低估 5–10%”未记录对应算例与置信范围，撤销普遍断言 | 适用范围须对应具体公式版本及其参考样本，不能只看单个 Cb 阈值 |
| QM 适用性 | 需同时核对 Cp、B/T、体积系数、Fn 和长度定义；不能用 Cb 代替表轴 Cp | 待实现独立对照并核对完整形状参数；缺输入必须显式估算 |

→ 当前计划保留 Taylor-Gertler 并增加 Holtrop 对照；比较时分别列出摩擦线、附体、相关修正和推进效率的定义，不能把不同定义的分量直接当作同一个物理量。

核对依据：[MARIN 的 1982 年原论文摘要](https://www.marin.nl/en/publications/an-approximate-power-prediction-method) 明确提到对细长军舰的扩展，同时限制于与研究样本相似的船型。摘要不提供完整数值域，不能据此宣布 Queen Mary 有效；原公式与基准仍是 Task 7 的必需验收内容。

**【2026-09-22 已落地】** Taylor-Gertler 表已数字化入库
（`cases/taylor_gertler_cr_table.json`，源自 Molland 附录 A3.8–A3.11 = Gertler DTMB-806）：
四维网格 Cp×B/T×∇/L³×Fn，缺格按可用角点归一化，表内 CR×1000 → scale 1e-3。
**2026-09-22 修正**：正常载荷输入统一使用同载荷湿面积估算，Cm=0.94 / QPC=0.55 显式为假设。
28.1 kn 预测 73,272 shp，相对试航参考低 11.72%，但试航载荷、原史料吨位单位未确认。
满载模型全部参数单列，反解 QPC=1.05434，旧“0.28”作废；撤销“史实口径互证”结论。
警告已贯穿曲线/Engines/HTML，缺剩余阻力时总阻力和功率为空。
详见 [计算修正与字段迁移](2026-09-22-calculation-integrity.md)。

**还得补的 7.3 输入**：lpp（垂线间长，∇/L³ 用它，**仍无源**）；Cr 的 QPC 误差带；
Holtrop 对照（旧记录提到 `_holtrop1982.pdf`，当前隔离工作区尚未找到该文件；须获取可核对原文与基准）。

---

## 3. 参考材料的三个洞（实现前必须补）

1. **Guns 的 Battery 子页截图从未捕获**——而那里才是全部输入（每门炮重/座圈/弹药/锁定）。
   现有 `02_Guns.png` 只有 Summary 输出页。**要么跑本地 `SpringSharp3b3.exe` 补截图，要么靠外部数据源**。
2. 七处 SPEC §5 的笔误/遗漏已按图纠正（如 Hull 页输出还含 Normal/Max volume；
   Weapons 页的 Misc weight 五分区；Armour 页 Length/Height 是输入）。
3. 要做**黑盒对照**（SPEC §7.3，"最有价值的一步"），本地 `SpringSharp3b3/` 就有可执行文件，
   且这台机器上跑过（工作区有截图）。**纯人肉字段清单有上限，跑起来才有权威对照。**

---

## 4. 当前结论与实施顺序

1. 现有基础计算能运行，产品 1.0 尚未完成；325 项基线回归通过不替代界面、完整案例及发布验收。
2. 先建立项目、单位、警告与迁移契约，再实现完整三轴重量和载荷；Queen Mary 缺项可透明估算，不得用补差重量强行匹配吨位。
3. 由同一载荷推进平衡浮态、稳性、简化破损和阻力；验证方法的适用性、缺值与估算传播。
4. 核心接口稳定后交付本地交互界面、独立发布包和端到端证据。用户已批准继续界面开发，旧“网站搁置”约定已被此次目标替代。
5. 1.0 明确不包括完整耐波性、结构强度及历史造价；因此完成当前目标也不等于逐项全面超越 SpringSharp。
