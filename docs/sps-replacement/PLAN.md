# Plimsoll 改进计划

> **2026-09-22 1.0 目标生效**：本文件后续阶段保留为历史记录。执行顺序以 [1.0 实施计划](../superpowers/plans/2026-09-22-plimsoll-1.0.md) 为准，状态以 [当前状态](../plimsoll-1.0/current-status.md) 为准。
> 用户已授权恢复本地 Web；旧“覆盖 13%”“界面搁置”等表述不再代表当前约定。历史勾选不证明新的 A–G 验收已通过。

> 范围：**只做 Plimsoll**。游戏侧的接入（`ShipFloatPrototype` 换数、`hydrostatics.json` 写回等）
> 不在此计划内，待 Plimsoll 自身稳定后再单独立项。
>
> 长期任务的推进方式：**每完成一项就回写本文件（勾选 + 记录结论）并提交**，
> 任何中断都能从勾选框接着跑。能并行的调研派后台子代理。

图例：`[ ]` 未开始 · `[~]` 进行中 · `[x]` 已完成 · `[-]` 已搁置（附原因）

---

## 2026-09-22 计算完整性修正（当前口径）

- [x] 修复矩形舱进水重心与无水 FSC，同时修复 GZ 舱室适配旁路。
- [x] 阻力逐点警告、缺格和估算标记传递至曲线、Engines 快照与 HTML；缺剩余阻力时总量置空。
- [x] 正常载荷输入共享，湿面积改为同载荷估算；满载模型单列，撤销“史实 Cm / 已互证”的结论。
- [x] 重生成三例破损结果、L0/GZ、型线系数、Engines、阻力及曲线。
- [x] **325 项回归通过；6/6 变异被捕获并恢复。**

详见 [计算修正与字段迁移](2026-09-22-calculation-integrity.md)。以下阶段记录中的旧基线和旧数值属于历史记录；冲突处以上述文档为准。

## 如何续接（给下一个会话读）

**仓库根**：`C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17`
**解释器**：`C:\Users\杨睿\.workbuddy\binaries\python\versions\3.13.12\python.exe`

### 按顺序读这四份，不用问任何人

1. **本文件** —— 阶段清单与勾选框。**下一个未勾选项就是下一步。**
2. `docs/sps-replacement/COVERAGE.md` —— **SPS 七页覆盖度检查表**（对标到哪了，一查便知）
3. `tools/plimsoll/README.md` —— 当前状态、已完成的 L0/L1、验证方式、诚实限界清单
4. `tools/plimsoll/cases/queen_mary_1913.json` —— 主案例，每个数值都带来源与口径说明
5. `docs/sps-replacement/SPEC.md` —— 架构原则与最终目标

### 历史基线（2026-09-21 晚；当前见上方修正）

- 最新提交见 `git log -1`，工作区干净
- 一键回归 **311 项全绿**：`"$PY" tools/plimsoll/run_all_tests.py`
  （…test_resistance 37 = **7.3 阻力/曲线**；test_engines 16；test_generic_ship 11 = 通用性契约）
  （test_weights 15 = L2；test_armour 20；test_guns 18；test_hull 16；test_freeboard 16；
  test_weapons 17；test_engines 14 = Engines 页；test_generic_ship 11 = **通用性契约**）
- **SPS 七页全部到 ◐ 以上**（2026-09-22）：Hull 基本齐 / Freeboard·Armour·Guns·Weapons·
  Engines·Performance 均为 ◐。剩 PLAN 7.3 阻力与功率、Hull 尾巴（`lpp_m`）、
  `offsets.py` 的 `DECK_Z_DEFAULT` 清理三条尾巴。

- [x] **7.2d Hull 页补齐（湿面积 / 长宽比 / 自然航速）**（v0 已完成 2026-09-22）：
  - `hull.py`：湿面积两法（Mumford 经验式 L0 + 逐站湿周长积分 L1，**积分必须扣除裁剪补出的
    水线闭合边**——否则方箱会多出 10×L 的假面积，测试专门守这个坑）；Length:Beam 定义式；
    自然航速**两口径并列**：Froude 兴波速度（有源）+ SPS 惯例 1.09·√L_ft（**estimate，
    常数无公开出处，标警告**），附 Fn 便于判断适用性。
  - QM 湿面积：正常载荷经验式现为 6147.6 m²，满载模型积分 6407.9 m²；
    两者载荷不同，撤销原“差 4.2% 可互证”的表述。L:B 7.852；
    自然航速 28.8 kn（SPS 口径）vs Froude 35.43 kn。
  - 测试 16 项（两轮变异验证：湿周长忘扣水线边 4 项红、经验式丢船长 3 项红）；
    `hull.py` 已纳入通用性护栏的核心文件清单。
- [x] **7.2e Freeboard 页**（v0 已完成 2026-09-22）：
  - `freeboard.py`：加权平均干舷 `f̄ = Σ(L段·f段)/ΣL段`；逐段长度 %Lwl→m；
    **每段输出甲板浸没角 `atan(f/(B/2))`**（与 cli 的 GZ 告警同一判据，<15° 就警告）；
    `from_depth(D, T)` 给型深口径的干舷。
  - **QM 无外部文献源**（Navypedia/维基都不列型深/干舷）→ 全部由模型包围盒推得，
    **全标 estimate**：型深 15.0 m（Hull z 跨度）→ 主甲板干舷 6.5 m；
    Forecastle 58.4%/8.90 m/33.3°、Quarterdeck 41.6%/7.12 m/27.7°；平均干舷 8.16 m。
  - 测试 16 项（两轮变异验证：加权丢长度 2 项红、浸没角半宽写错 1 项红→已加精确锚）；
    `freeboard.py` 已纳入通用性护栏核心清单。
- [x] **7.2f Weapons 页**（v0 已完成 2026-09-22）：
  - `weapons.py`：鱼雷清单（管数/携带数/直径/布置 + **战斗部装药总重**）；水雷/深弹
    （**没给 = None，显式 0 才是"不装备"**）；Misc weight 五分区（小计 + 占排水量 +
    >25% 告警 + **缺 kg_m 的 L2 接口警告**）；`sps_view()` 整页视图。
  - QM 鱼雷有源：2 × 533 mm 水下舷侧管、14 枚 Mk II***、战斗部 400 lb (181 kg)
    → 装药总重 2.534 t。**单雷全重/雷长未采集 → 置 None 并警告**（不用装药冒充全重）。
    水雷/深弹/Misc 五分区无文献源 → 置空。来源冲突（400 vs 515 lb；10,000@29kn vs
    10,750@31kn）已在案例里并列记录。
  - 测试 17 项（两轮变异验证：装药丢携带数 3 项红、缺项冒充 0 3 项红）；
    `weapons.py` 已纳入通用性护栏核心清单。
- [x] **7.2g Engines 页（只做有源部分）**（v0 已完成 2026-09-22）：
  - `engines.py`：轴数/主机/锅炉/功率/航速/燃料/续航；`kW = shp × 0.7457`（精确换算）；
    `%Coal`、Bunker、续航（含"未注明对应航速"警告）。
  - 量级校核（estimate）：**海军部系数 `C = Δ^(2/3)·V³ / P` = 248**（军舰 200–300 区间，
    证明功率/航速/排水量自洽）+ 最大航速 Froude 数。
  - **明确不做并点名**：Friction/Wave resistance（→ **PLAN 7.3** Holtrop-Mennen/Taylor）、
    Engine weight（无源）、Displacement factor、Engine factor（SPS 自有系数无公开定义）。
  - **踩坑与修正**：初版把导出量在 trace 与 values 里**各算了一遍**（双源头），
    导致变异验证改了一处而测试仍绿 —— 已重构为单一变量共用，重做变异才真正变红。
    **教训：变异没打红时，先怀疑"是不是有两个真值来源"，而不是怀疑测试没用。**
- [x] **7.2h 两条尾巴清理**（2026-09-22）：
  - **`offsets.py` 的 `DECK_Z_DEFAULT = 5.10` 已删除**：`section_profile` /
    `halfbeam_at` / `build_hull` 的 `deck_z` 改为**必填**（甲板高是船的数据，不是代码默认，
    否则别的船会静默拿到 QM 的 5.10）。调用方（cli 从型线文件/案例取、测试显式给、
    `gen_qm_offsets.py` 生成器内定义）已同步；**型线 JSON 的 md5 不变**，行为无回归。
  - **水线长可从型线真算**：`hull.waterline_length(hull, z)` —— 逐站半宽 >0 的纵向跨度，
    **端点线性插值到零**（不插值会退化成取整站位置，变异验证守住）。QM 型线 z=0 得
    213.4 m（满载吃水口径）> 案例正常吃水 212.8，方向自洽；`lpp_m` 仍无源，未编造。
  - 测试 16 → 21（test_hull）；变异验证：端点不插值 1 项红。
- **剩唯一尾巴：PLAN 7.3 阻力与功率**（Holtrop-Mennen / Taylor）—— 与 Engines 页的
  Friction/Wave resistance 是同一件事，单独立项做。

### 通用性契约（2026-09-22 用户指令，SPEC §2.7）

**Plimsoll 是通用求解器，能解任何船、任何设定；Queen Mary 只是案例，不是前提。**
本次落实：核心源码扫描护栏（船只字面量即红，变异验证过）；QM 型线物化为
`cases/queen_mary_1913_offsets.json`（CLI 不再扫描仓库路径/解析生成脚本）；
新增非 QM 解析靶船 `cases/generic_test_steamer_1910.json` 全链路测试。
- **通用性遗留已清（2026-09-22）**：~~`offsets.py` 的 `DECK_Z_DEFAULT=5.10`~~ 已删除，
  `deck_z` 改为必填。
- 跑主案例：`"$PY" tools/plimsoll/cli.py tools/plimsoll/cases/queen_mary_1913.json --gz -o <out.json>`

### 下一步

**已合入 master（2026-09-21）**：
- 阶段 **2.2 纵倾平衡**：`solve_trim_equilibrium`（体积+LCB 双门闩）
- 阶段 **3 FSC**：`freesurface.py` + `gz_curve(free_surface_tanks=)`

### 下一步

**已合入 master**：2.2 纵倾平衡 · 3.x FSC · 4.1 进水组合（`cc266fe`）。

**本分支 `feature/plimsoll-damage-loop`（长任务，用户离开期间）**：
- [x] **4.2 破损浮态** — `damage.solve_flooded_equilibrium`（4.1+2.2；KM 用 upright 近似；小角度横倾）
- [x] **4.3 剩余 GZ** — `damage.remaining_gz_curve`
- [x] **4.4 场景回归** — `cases/damage_scenarios.json` + `run_damage_scenarios.py`
- [x] **5.1 L1 integrate trace**
- [x] **5.2 包入口** `plimsoll/__init__.py`
- [x] **5.4** `run_all_tests.py` 一键回归（126 项）

**合入后候选**：5.3 sweep CLI；7.1 装甲穿深校准；真实型线；游戏侧接入。

**纪律**：舱室几何显式 L×b；FSC 分母 Δ′；4.2 KM 为 estimate；变异验证。

**变异验证纪律**：改数值实现后，先确认相关测试对设计缺陷会变红。

### 三条别重新踩的坑（都是这一晚踩出来的）

1. **两套坐标基准并存时，任何跨基准的量必须显式换算。**
   型值表船体：龙骨 z=−9.9、设计水线 z=0；合成参照船体：龙骨 z=0、水线 z=T。
   KB/KG 自龙骨量，积分出的 zb 相对水线量 —— 混用会让 GM 变成负数。
   同一晚踩了两次（KB、甲板浸没角）。
2. **外部摘要里的具体数字必须回源核对。** 我照搬调研摘要说"平行中体恰好 13.60 m"，
   回查原表发现 y=+30 处已收到 13.55。
3. **选来源要看它在多源中的位置，孤例必须存疑。** 我把 LWL 取成 Tyne 的 675 ft，
   而其余五源聚在 213–214 m —— 一个孤例把我带偏，还连累 `Cb` 反推成了自证。

### 关于"无人值守"

本进程**不能**在你离开后自己继续：一轮对话结束即停止。能持久的只有
① 后台子代理（有界任务）② 后台 shell 任务 ③ 定时自动化（到点开**新会话**）。
故本文件与上述四份文档必须自足 —— 新会话读它们就能接上，不需要任何口头上下文。

---

## 阶段 1 · 数据修正与基准统一

- [x] **1.1 修正 LWL：205.7 → 212.8 m**（2026-09-21 完成）
  六源核对结论：LWL = 698 ft = 212.75 m（worldwar1.co.uk 明写 "698 feet waterline"），
  LOA = 214.4 m。`lwl_m = 205.7` 采信了孤例（Tyne 的 675 ft）。
  **连带发现：`Cb` 也必须同步改** —— 原值 0.551 是从错误的 LWL 反推的（循环论证），
  只改 LWL 会让排水量虚高 3.4%。改为 **0.533** 后偏差回到 **+0.04%**。
  **护栏**：`test_hydrostatics.py::TestQueenMaryCase::test_displacement_matches_input`
  已天然守住这条耦合（只改 LWL 会让偏差变 3.4%，测试立刻红）。
  意外收获：改对 LWL 后 L0 的水线面为 4613.5 m²，与项目现有常数 4610.4 只差 **0.07%**
  （此前差 3.3%）—— 那个常数一直是对的。
  另发现：型值表船体在满载吃水 9.9 m 上积分得 31,717 t，对实船满载 31,650 t 差 **0.21%**；
  Cb 0.5405 vs 实船 0.5408，差 **0.06%**。**模型体积特性可信**（但形状分布仍未验证）。
- [ ] **1.2 吨位单位定性**：史料 26,770 是长吨还是公吨？差 1.6%。
  验收：在案例文件里显式声明 `displacement_unit`，并说明选择依据。
- [ ] **1.3 口径字段拆分**：把单一 `length_m` 拆成 `lwl_m / loa_m / lpp_m`（若可得）。
  验收：案例文件与契约建议同步。

## 阶段 2 · 浮态自由度：加上纵倾

现在 `solve_waterline` 只能平移水线，不能倾斜 —— 船会纵倾，战损尤其。

- [x] **2.1 积分器支持纵倾**（2026-09-21 完成）
  水线在船体坐标里是一张平面 `z = x·tanθ + y·tanφ + d`，逐站截距
  `d(x) = d + x·tanθ`。**固定 x 时水线在剖面内仍是直线**，与纯横倾只差截距
  —— 故共用同一套裁剪逻辑，不是新算法。
  **符号约定：θ > 0 = 艏倾（bow down）**，已写进 docstring。
  顺带补齐：`integrate` 增出 `xlcb`（浮心纵向位置，阶段 2.2 要用）；
  水线面面积乘 `√(1+tan²φ+tan²θ)`（斜平面正确因子，原先只处理了横倾）。
  验收：方箱带纵倾的闭式解 —— 体积**逐位精确**、KB 到 4 位小数（含二阶项
  `tan²θ·L²/(24T)`）、LCB 到位、Awp 到位。测试数 72 → **79**。

  **变异验证（重要发现）**：把纵倾去掉后，体积仍是 5000.0000 —— **测不出**。
  体积对纵倾一阶不敏感（tanθ 项在对称区间积掉）。真正守住实现的是
  LCB（5.8205 vs 0）、KB（2.6016 vs 2.5）、Awp（1000.61 vs 1000）。
  与 5.0 那处假绿同类：**最直觉的断言往往抓不住 bug**，已写进测试注释。
- [x] **2.2 纵倾平衡求解**（2026-09-21 完成）
  给定排水量与 LCB(=LCG)，嵌套求根解出 `(d, θ)`：内层 `solve_waterline` 解 d 使体积达标，
  外层二分 θ 使 `xlcb` 对齐 LCG；θ 默认 ±15°，可扩到 ±30°，不可达/未收敛一律 `ValueError`。
  API：`StationedHull.solve_trim_equilibrium` + `geometric.solve_trim_equilibrium`。
  验收：方箱闭式解（d*=keel+T，tanθ=12·T·LCB/L²，θ 与 LCB 同号）+ 参照船体已知 θ 往返还原；
  变异验证：残差强制为 0 → 4 项测试变红。测试新增 `test_trim_equilibrium.py`（10 项）。
  ⚠️ 数值 LCB 的梯形积分对二次被积不精确（~1e-3 相对），θ 与解析闭式解比用相对误差，不要用逐位。
- [ ] **2.3 水线长与排水量的耦合检查**：大纵倾下 LWL 会变，须交代其对结果的影响。

## 阶段 3 · 自由液面修正（FSC）

进水舱的自由液面会显著抬高重心等效位置。

- [x] **3.1 单舱自由液面惯性矩**（2026-09-21）
  `tools/plimsoll/freesurface.py`：矩形舱 `i = L·b³/12`；
  空/满舱 `i_eff=0`；`FSC = Σ(ρ_i·i_i)/Δ`。
  验收：矩形舱解析解 + 双舱线性叠加 + 空满为零（`test_freesurface.py`）。
  ⚠️ 游戏侧 `buoyancy_compartments.json` **无 L×b**，本阶段输入必须显式给尺寸；
  由舱容反推形状属阶段 4，禁止猜几何。
- [x] **3.2 并入 GM 与 GZ**（2026-09-21）
  `apply_fsc` → `KG_eff = KG+FSC`；`geometric.gz_curve(..., free_surface_tanks=)`。
  验收：与手工 `gz_curve(hull, kg+fsc, ...)` 逐点一致；无 tanks 时行为不变；
  GZ 下降量 ≈ `FSC·sinφ`。

## 阶段 4 · 破损稳性（**阶段性目标**）

这是 Plimsoll 真正要交付的能力，也是游戏侧进水系统最终需要的东西。

- [x] **4.1 进水组合模型**（2026-09-21）
  `damage.py`：矩形舱 δ=ρ·μ·f·L·b·H，kg_f=z0+f·H；合成 KG_solid'；
  FSC=Σ(ρi)/Δ'（分母为**进水后**排水量）；KG_eff=KG_solid'+FSC；可选 GM'。
  舱室必须显式 L×b×H，禁止从 compartment JSON 猜几何。
  验收：`test_flood_combination.py` 手算对照 + Δ' 分母差分测试。
- [x] **4.2 新浮态求解**（2026-09-21 · damage-loop）
  `damage.solve_flooded_equilibrium`：Δ′/LCG → 2.2 纵倾平衡；KM≈upright(d)；
  GM′=KM−KG_eff；小角度 heel=atan(Σδy/(Δ′·GM′))。GM≤0 时 heel=null 并标记。
- [x] **4.3 剩余 GZ 曲线**（2026-09-21 · damage-loop）
  `damage.remaining_gz_curve`：KG_eff + V* 下 GZ 表，max/range。
- [x] **4.4 场景回归**（2026-09-21 · damage-loop）
  三场景 JSON + `run_damage_scenarios.py` 落盘 `cases/out/*.result.json`，确定性可复现。

## 阶段 5 · 工程化与可追溯

- [x] **5.0 基准与静默隐患加固**（2026-09-21 完成 · 独立复核查出）
  派子代理对全部源码做了一次只读复核，找出 4 项隐患 + 1 处假绿：
  1. `hydrostatics_upright(hull, draught)` 的参数名骗人 —— 它要的是**船体坐标 z**，
     传真实吃水会静默返回整只船体（体积 55229、I_T 归零、KB=8.85）而不报错。
     → 改名 `waterline_z`，并加区间校验（keel ≤ z ≤ top）与「I_T 归零」校验。
  2. `draught_m` 在型值表船体下恒为 0.0。→ 改为 `waterline_z − keel_z`（自龙骨的真实吃水），
     另增 `waterline_z_m`。
  3. **一处假绿**：`test_initial_slope_matches_gm` 里 `keel_z` 在等式两边同号相消，
     把 keel_z 改成 0 甚至 12.3 照样过。→ 新增锚在**源数据绝对值**的断言
     （龙骨 == 型值表第 4 列最小值 == −9.90），并保留原测试但标明它只是内部自洽校验。
  4. `_waterline_halfbeam` 在水线落在定义域外时静默回 0 → I_T/BM 归零不报错；
     且 docstring 与实现不符。→ 补齐退化情形（水线切在剖面顶点）与零值报错。
  5. box/reference 测试的 keel_z 恒为 0，`−keel` 是恒等变换 → **基准错误天然不可见**。
     → 新增 `TestDatumShift`：把解析方箱整体下移到 z∈[−5,15]、水线在 0，
       用闭式解（KB=T/2、BM=B²/12T、GZ 闭式）验基准。

  **变异验证**（证明新测试不是假绿）：把 `keel_z` 分别改成 0.0 / 12.3 / −8.0 ——
  前两者被新断言与新区间校验抓住；**−8.0 只能被「锚源数据」那条抓住，
  而「KB/吃水落在 0.40–0.70」抓不住**（比值 0.513 在区间内）。
  这印证了复核的判断：光靠"数值在合理范围内"不够，必须锚在源数据的绝对值上。

  测试数 63 → **72**，全绿。
- [x] **5.1 L1 输出补 trace**（2026-09-21 · damage-loop）
  `integrate()` 返回 `trace`：volume/yb/zb/xlcb/awp 均含 formula/source/estimate。
- [x] **5.2 包化**（2026-09-21 · damage-loop）
  `tools/plimsoll/__init__.py`；脚本式 cwd 仍可跑（测试路径不变）。
- [ ] **5.3 批量模式**：`plimsoll sweep cases/*.json`（SPEC 已写，未实现）。
- [x] **5.4 一键回归**（2026-09-21 · damage-loop）
  `tools/plimsoll/run_all_tests.py`：discover 全部 tests，汇总 `PLIMSOLL_REGRESSION`。

## 阶段 6 · 数值精度遗留

- [ ] **6.1 梯形积分 vs 精确多面体差 0.67% / −1.17%，根因未查明。**
  候选方向：换成 Simpson / 棱柱公式；或直接实现精确多面体体积。
  验收：差异降到可解释的离散误差量级（<0.01%），或给出明确的根因说明。

## 阶段 7 · 功能扩展（优先级低于阶段 2–4）

> **2026-09-21 路线修正**：经 SPS 覆盖度核查（见 **COVERAGE.md**），SPS 公共七页只覆盖 ~13%，
> 而 L2（重量分组）是 Guns/Armour/Weapons 三页的共同前置 —— 故 **7.2 升为当前主线**，
> **7.5 网站搁置**（用户指令），直到覆盖度六页至少到 ◐。

- [ ] **7.1 L4 穿深校准**：装甲验收标准数据已录入 `data/british_armour_standards_1908_1912.json`，
  至今一条未用。拟用 de Marre / Thompson F 反解系数复现"刚好穿透"边界，
  **必须在未参与拟合的表项上回测**。
- [~] **7.2 L2 重量分组与重心**（v0 已完成 2026-09-21）：
  - 合成引擎 `weights.py`：质量矩加权 KG（**基准强制 `datum: keel`**——坐标基准教训的第三道闸）、
    逐组小计、trace 全套、覆盖率对照。
  - **关键行为：合成质量不足排水量 95% 时拒绝算 GM** —— 用残缺 KG 算出漂亮 GM 是本项目最该防的错。
  - 装甲组实数据：厚度带 wiki 来源（`queen_mary_v3/armour_zones.json`）+ 面积由模型包围盒
    按 role 选面推得（`tools/gen_weights_case.py` 可复现，曲率系数 1.10，炮管不计装甲）。
    **合计 6,820.7 t = 排水量 25.5%，正落史实带（狮级 22–28%）**；装甲合成 KG ≈ 9.86 m。
  - 测试 15 项（含变异验证：加权丢失 4 项红、删 GM 闸 1 项红）。
  - **待做**：武备组（弹重 1400 lb 已有，炮塔/炮架重量缺）、动力组（全缺，需外部采集）、
    船体舾装组（可由型值表湿面积推）。
- [x] **7.2b Armour 页（SPS）**（v0 已完成 2026-09-21）：
  - `armour.py`：逐区 `W = 面积 × 厚 × ρ`（ρ=7850 带出处），按 SPS 行结构分组
    （Main/Ends/Upper/Bulge/Torpedo bulkhead + 甲板/炮座/司令塔/其他），`sps_table()` 出表视图。
  - 与 SPS 的差异（诚实记录）：面积优先用模型包围盒逐对象选面累加（比 SPS 的 L×H 口径保真），
    Length/Height 只作展示；行只给 L×H 时退化为 SPS 口径。
  - 生成器 `tools/gen_armour_case.py` **直接 import gen_weights_case 的选面规则**（同源同数），
    一致性由测试把守（与 L2 装甲组差 < 0.5 t）。
  - 诚实缺口：**炮塔装甲未计入**（turret_face 在 manifest 里无选面 role，L2 同）；
    Bulge 行置 None + 警告不冒充 0；Armour deck 按厚度层两行，按位置分段待补。
  - 测试 20 项（含两轮变异验证：丢密度 4 项红、Bulge 冒充 0 5 项红）。
- [x] **7.2c Guns 页（SPS）**（v0 已完成 2026-09-22）：
  - `guns.py`：SPS Weights 表（行 Guns/Mounts/Armour/Total/Broadside lbs/Broadside kg/Magazine；
    列 Main/2nd…）。`sps_table()` 直出表视图；lb→kg 用国际磅定义 0.45359237（精确）。
  - **外部数据采集完成**（此前的缺口）：主炮 76.102 t/门（NavWeaps，不含炮闩）、
    BII 座 600 t（**BII* 未单列 → 沿用并标 estimate**）、弹 1,400 lb、装药 297 lb MD45、
    设计储弹 80 发/门；副炮 4" Mk VII 2.134 t/门、弹 31 lb、150 发/门。
  - 数量（8 管/4 塔/16 副炮）来自 `ship_contract.json`（模型有源）；齐射 = 单舷 8 门（四塔全中线）。
  - 诚实缺口：**Armour 行（炮塔装甲重）置 None + 警告**——与 Armour 页同缺口；
    副炮装药未采集（Magazine 只算弹重，偏低，有警告）；
    设计 80 发/门 vs 战时 110 发/门（主炮 Magazine 492.6 vs ≈677.6 t）与 Jutland 名录
    的 661 t 全舰 allowance 三者口径矛盾，已在案例 `_note` 里记录，基准取 as-built。
  - 测试 18 项（含两轮变异验证：齐射丢门数 3 红、Magazine 丢门数 6 红）。
- [~] **7.3 阻力与功率**（Holtrop-Mennen / Taylor）—— **地基已打（2026-09-22）**：
  - **方法选择（已定，理由见 COVERAGE §4）**：主力用 **Taylor-Gertler**（母型是军舰
    装甲巡洋舰 Leviathan、适用 warships、QM 的 B/T 与 ∇/L³ 都在范围），
    **Holtrop-Mennen 作对照**（QM 的 Cb=0.533~0.547 **低于其下限 0.55**，文献明说
    "fine warship forms, accuracy degrades"，不得当主值）。两者摩擦口径不同
    （Schoenherr+0.4e-3 vs ITTC-1957+CA），比较前必须对齐。
  - **地基（已完成）**：`hull.form_coefficients()` 与 `hull.half_angle_of_entrance()`
    从型线**真算** ∇ / Am / LCB / **Cb / Cp / Cm / iE**，已物化为
    `cases/queen_mary_1913_formcoeff.json`。QM（满载口径 z=0）：
    ∇=30943.9、Bwl=26.8、T=9.9、Lwl=213.4、**Cb=0.5465 / Cp=0.7657 / Cm=0.7138**、
    iE=27.06°、S=6407.9。
  - ⚠️ **关键限界**：模型型线 **Cm=0.71 明显低于战舰常见 0.9+** —— 这是
    「体积/Cb 已验证、形状分布未验证」的量化证据。**阻力对 Cm/Cp 极敏感**，
    7.3 的结论必须带上这条限界（测试已锚住：型线改了会提醒重记）。
  - 半进流角**口径不唯一**（艏端切线/B·10/B·4 各派不同）：实现为显式约定
    （默认离中线 Bwl/10，参数可调），取不到就返回 None，**不编造**。
  - 测试 21 → 32（test_hull）；变异验证：Cp 分母写错 4 项红、钝艏编造角度 1 项红。
  - **历史实现记录（下列旧数值已由计算完整性修正替代）** `resistance.py` + `tools/gen_resistance_case.py`：
    - Schoenherr 摩擦线 `Cf = 0.4631/(lg Rn)^2.6`（Taylor 法配套）；
      QM @28.1 kn：Rn=2.59e9、**Cf=0.00136**（与 ITTC-1957 差 **−0.3%**，交叉校核通过），
      含 0.4e-3 粗糙度附加 → **Rf ≈ 1,209 kN**。
    - **由试航真值反解隐含剩余阻力**：83,000 shp × QPC 0.55 → R_total 2,355 kN、
      Rr 1,146 kN、**Cr ≈ 0.00167**（合理量级 1e-3–4e-3，剩余占比 49%）。
      已物化 `cases/queen_mary_1913_resistance.json`。
    - **剩余阻力图谱接入位已就绪**：`residual_from_table()` 四维（Cp、B/T、∇/L³、Fn）
      多线性插值已实现并有测试（对线性函数精确、越界只截断**不外推**）；
      **缺表时返回 None + 警告**。
  - **阻塞项（诚实记录）**：Gertler 1954 DTMB-806 的 Cr 图谱公开检索只有
    **OCR 乱码版本**（教科书附录 Table A3.9 之类）——**照乱码抄数等于编数据**，
    故暂不填表。需正规教材附录/原报告数字化后接入（数据进案例、核心不动）。
  - 测试 19 项（两轮变异验证：摩擦线指数改错 5 项红、缺表返回 0 冒充 1 项红）。
  - **★ 2026-09-22 突破：Taylor-Gertler 图谱拿到手了（表格版）**
    - 来源：Molland/Turnock/Hudson《Ship Resistance and Propulsion》**附录 A3，
      Table A3.8–A3.11（书页 495–498）**，数据原始出处 Gertler, DTMB Report 806 (1954)。
      用户提供 PDF（教科书），我用 `tools/parse_taylor_gertler.py` **按坐标解析**
      （该书把横排大表旋转 90° 排在竖版页上：存储坐标里「行沿 x、列沿 y」；
      且表内有大量缺格「—」，靠文本流 token 数会错列 → 必须按坐标归属）。
      解析结果与**原书页面逐格核对**（抽检 Cp=0.50 Fr=0.40、Cp=0.60 Fr=0.16、
      Cp=0.80 Fr=0.30 等行，含缺格位置全部吻合）。
    - 产物：`cases/taylor_gertler_cr_table.json`（四维网格 Cp×B/T×∇/L³×Fn，
      表内 CR×1000 → `scale: 1e-3`，缺格为 null）。
    - 核心适配：`residual_from_table()` 增加 **缺格按可用角点重新归一化**（缺格当 0 会压低阻力、
      崩掉会让链不可用）；`scale` 字段做单位换算。
  - **原互证结论已撤销（计算完整性修正）**：Cm=0.94 是假设，正常载荷与模型满载必须分列。
    正常载荷估算 Cr=0.00139587、反解 QPC=0.48554；满载模型反解 QPC=1.05434。
    原“QPC=0.28”错误。数值偏差仅作诊断，不再据其接近试航数据宣称验证通过。
  - 测试 19 → 29 项（表完整性 + 书上抽检值 + 缺格归一化 + QM 双向交叉校验）；
    变异验证：忽略 scale 2 项红、缺格当 0 3 项红。
  - **② 整条 R–V 曲线已完成（2026-09-22）**：`resistance.speed_power_curve()`
    + `tools/gen_speed_power_case.py` → `cases/queen_mary_1913_speed_power.json`
    （8–29 kn × QPC 0.50/0.55/0.60 三条带）+ 可视化
    `cases/out/queen_mary_speed_power.html`（自绘 SVG，无外部依赖）。
    - **当前同速对照**：正常载荷估算 28.1 kn、QPC=0.55 时为 73,272 shp，
      相对 83,000 shp 参考低 11.72%。试航载荷未知、吨位单位未确认；不据此宣称历史验证。
    - Fr<0.16 的低速点**端点截断不外推**（表中最低 Fr=0.16）；QPC 假定值写进每条警告。
    - `engines.sps_view(result, resistance=…)` 接口打通：Engines 页的 Friction/Wave resistance
      两格现在可填（值来自 resistance.py 并标来源；不传仍为 None，保持诚实留白）。
  - **待做**：① QPC 敏感性已在曲线里以三条带形式给出，误差带文档待写；
    ③ Holtrop 对照（原文在手，注意 Cb 越界）。
- [ ] **7.4 耐波性估算**：切片理论（最低优先级）。
- [-] **7.5 Web 界面**：**搁置（2026-09-21 用户指令）**——SPS 覆盖度仅 ~13%，
  网站会把"只有 Hull 一页"固化成看起来完整的样子。`feature/plimsoll-web` 草稿保留不删；
  另见复查报告（根目录 `复查_Plimsoll上网站前_2026-09-21.md`）的三条 P0，复工前必修。

## 搁置项

- [-] **真实型线图**：书（John Roberts《Battlecruisers》）国内不好买；NMM 未见本舰完整型线图。
  详见 `型线图资源.md`。**当前用内建估算表，来源标 `builtin_estimate`**，
  接入点 `hull_offsets.json` 已就位 —— 拿到型线随时替换，代码不用改。
