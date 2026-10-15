# 七页覆盖基线快照（2026-10-15 第一阶段修复后）

本页和对应 JSON 保存第一阶段的可重复覆盖审计。后续实现及其证据见
[概念估重与设计平衡当前覆盖](concept-design-coverage.md)。下文“未实现”和
“本轮未运行原程序集”均描述第一阶段，不能用来判定后续版本的能力。

本文件说明 `evidence/seven-page-binding-proposal.json` 在 2026-10-15 覆盖修复后的真实状态。
它不是完成度宣传，也不构成对 SpringSharp 3b3 的等价性证明。

## 证据边界

- 原始 191 条观察清单冻结未改：
  `.superpowers/sdd/2026-09-22-plimsoll-1.0/seven-page-fields.json`
  与 `evidence/seven-page-inventory.json`
  （SHA256 `b4b979b73b48a8e8b9f668375f4be0616ee3af5f882b72ede05b46b32f007d07`）。
- 反编译来源：`SpringSharpMono` 3.0.3032.29945，
  `SpringSharp3b3.exe` SHA256 `82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc`。
  本轮是**源码转写比对**，没有运行原程序集的比对执行。
- 因此：`verified_records = 0`。任何“已有适配器”“已有绑定”“已获批排除”
  都**不计入**已验证的 SPS 等价。

## 本轮撤回的对应关系

| 记录 | 旧状态 | 新状态 | 撤回理由（恢复证据） |
| --- | --- | --- | --- |
| `performance.set_trim` | `implemented_as_constraint_study` | `unavailable_semantic_mismatch` | SPS「Set Trim」是 0..100 整数经验稳当性调整（`PerformanceControl.cs:239,259,343,419`），不是目标纵倾角 |
| `performance.steadiness` | `implemented_input_conditional` | `unavailable_semantic_mismatch` | SPS `steadinessAdj = min(steadiness × seaboat, 100)`（`:419`）是 0..100 评分；`loaded_roll.period_s` 是秒，量纲不同 |
| `hull.derived.natural_speed` | `unavailable_method_undefined`（旧标签）/ `computational_adapter_required` | `method_known_parity_not_implemented` | 方法已查清：SPS 为 `sqrt(lengthEffect)`，艉型条件（`HullControl.cs:1345-1362`）；旧“方法未定义”标签撤回，但**没有**版本化兼容实现，也未验证 |
| `guns.battery_selection.editor_fields_unknown` | `unobserved_source_limit` | `source_expanded_not_implemented` | 观测清单漏拍；现由 `evidence/gun-editor-source-supplement.json`（v1.0.0）逐控件转写 |

撤回的绑定不删除，改为 `historical_rejected_bindings`（含撤回阶段与理由），
并用 `related_plimsoll_studies` 明确指出这些路径**实际**是什么。
`disposition_history` 保留原始提案、2026-09 核心复核与本轮三个阶段的旧判定。

## 当前状态分布（191 条）

| 处置 | 条数 |
| --- | --- |
| `implemented_input_conditional` | 87 |
| `existing_binding_conditioned` | 48 |
| `excluded_by_approved_scope` | 26 |
| `presentation_deferred_historical_phase` | 16 |
| `implemented` | 5 |
| `implemented_canonical_unit` | 5 |
| `unavailable_semantic_mismatch` | 2 |
| `method_known_parity_not_implemented` | 1 |
| `source_expanded_not_implemented` | 1 |

语义关系分布：`same_quantity_different_derivation` 99、`declaration_or_ledger_binding_only` 33、
`scope_excluded_not_a_replacement` 26、`presentation_phase_historical_not_retested` 16、
`same_concept_canonical_unit_variant` 7、`related_measure_not_equivalent` 6、
`different_semantics_unimplemented` 2、`method_known_not_implemented` 1、
`source_expanded_not_implemented` 1。

验证状态：`not_re_audited_in_this_review` 161、`scope_excluded_not_verified` 26、
`re_audited_against_recovered_source_2026_10_15` 4。

**没有任何一条**语义关系是“已验证等价”。161 条未在本轮重审，其结论沿用 2026-09 复核，
本轮不为其编造验证。

## 修复的两个生成器缺陷

1. 旧脚本只在状态以 `implemented` 开头时才写回 `current_disposition`，
   于是争议记录即使被改判也仍然显示 implemented。现所有 191 条都写入本轮处置
   （94 条与上一版不同）。
2. `presentation_deferred` 是 2026-09 纯核心阶段的历史状态，不是今天的界面完成度。
   现记为 `presentation_deferred_historical_phase`；本轮没有为这些记录跑界面测试，
   因此不声称界面已验证。

## 自然速度

- SPS：`speedNatural = sqrt(lengthEffect)`，
  `coSharp = 0.4·(B_bulges·6/L)^(1/3)·√(Cb/0.52)`，
  `lengthEffect` 按艉型取 `L`、`L + 0.5·B/coSharp` 或 `L + B/coSharp`。
- Plimsoll `hull.natural_speed()` 的 1.09·√L_ft 已改称**旧独立启发式**
  （数值不变，向后兼容），模块与文档不再声称它是“SPS 惯例”。
- 本阶段**不实现**新的自然速度数学。

## 炮组编辑器补充（`gun-editor-source-supplement.json`，v1.0.0）

- 35 个控件、12 个方法：口径（in/mm 换算）、身管长度（口径倍数）、设计年代
  （CCYY 1850-1950，`dateGunAdj = √dateAdjCalc`）、炮种、炮座种、总座数、两组各自每座门数、
  布置、高炮座/甲板座/水下座（组 1 甲板座与三条门数输出为只读推导）、`2 mounts up` 与
  `Lower deck` 两个超射复选框、三项装甲厚度、装甲重量、弹重 lb/kg 与三态锁定、每门储弹、
  说明文本、两张示意图。
- 方法：`shellWeightCalc`（弹重估计，lb）、`gunWeightCalc` 炮重/炮座重分支、
  `weightAdjCalc`/`perMountCalc`、`mountsCalc` 两组拆分、`super` 超射比、`freeGunCalc`、
  `layoutCalc`、`armWeightCalc`/`diameterCalc`、`magazineCalc`、`gunString`、`gunWarningsAll`。
- **Plimsoll 侧先说已有的**（本轮已对照现行源码逐条核实，全部 35 条
  `plimsoll_audit_state = verified_against_current_source_2026_10_15`）：
  - `installed_guns` / `installed_count`：真实生效的声明装舰门数，
    `GunsEditor.tsx` 可编辑，`systems.py _declared_count`(74) 接受三种字段并驱动质量模型，
    `systems.py:240` 与 `page_rows.py:769` 回报该数值。**不得与炮座数混同。**
  - `rounds_per_gun`：声明每门储弹，`systems.py:115-130` 校验并驱动弹药装药质量，
    `page_rows.py:654` 回报 `per_gun_shell_kg`。
  - `broadside_guns`、`facts.projectile_mass_kg`（`page_rows.py:649` 起的报告/质量输入）、
    `facts.calibre_m`、`facts.mount_count`（合同允许并校验）、`rotating_armour_component`
    （选定炮座质量的非加和拆分）。
- **真正缺的只有估算链**：Plimsoll 不会由口径、身管长度、设计年代、炮种、炮座种或两组
  高/甲板/水下布局反推炮重、炮座重、弹重、弹药或炮塔装甲。
  35 条覆盖分布：`no_field_in_enumerated_weapon_contract` 13、
  `not_a_user_input_in_sps` 9、`declared_fact_not_read_by_current_computation` 6、
  `declared_input_no_estimation` 6、`derived_readout_from_declared_inputs` 1。
- 声明“Plimsoll 没有某字段”只在该字段确实不在
  `project_extensions.py` 的 `WEAPON_FIELDS` / `PAGE_ROW_TYPED_FIELDS` 枚举表内时作出
  （可验证）；其余情况标 `not_reaudited`，不以未经检查的“缺失”充数。
- 转写保真度：恢复代码中的经验常数（`1.9830943211886`、`main.INCH = 0.0185`、
  `1.2444444/2240`）按原样记录，不对其量纲基础作解释；SPS 的
  `POUNDS2KG = 0.45359236` 与 Plimsoll 使用的精确 `0.45359237` 相差 1e-8，已在条目中注明。

## 活跃元数据与历史元数据

争议记录（`performance.set_trim`、`performance.steadiness`、`hull.derived.natural_speed`）
的 `limitation`、`required_stages`、`provenance_bindings`、`canonical_inputs`、`evidence`
已按恢复语义改写：**活跃 `required_stages` / `provenance_bindings` / `canonical_inputs` /
`result_bindings` 一律为空**，因为没有任何阶段提供该 SpringSharp 控件。
被取代的旧表述（`equilibrium` / `hydrostatics` 阶段要求、`roll_gyration_coeff` 与
`lwl_m` 规范输入、旧 limitation 原文）逐字保存在 `historical_metadata`，
旧绑定路径保存在 `historical_rejected_bindings` 并附撤回理由。

## 未决与后续（本轮未做）

本节只列**尚未实施**的替代缺口。本次请求的覆盖基线修复（撤回错误对应、
更新自然速度方法证据、展开炮组编辑器）**已完成**，不是待办项。

- F04 武备/机械自动估重、F05 强度/耐波/空间/造价/乘员概念筛选：仍是核心替代缺口。
- 自然速度与稳当性的 SPS 兼容口径：需要版本化方法并对照原程序集验证后才可声明等价；
  本阶段**不实现**新数学。
- `.sship` / SpringSharp 项目迁移：未实现。
- `verify quick` 的发布期 `os.replace` 失败属交付可靠性问题，与本覆盖基线无关。

## 再生成

```powershell
& './web/backend/.venv/Scripts/python.exe' -B tools/plimsoll/tools/reconcile_seven_pages.py
```

生成器是冻结策略的纯函数：连续两次运行输出逐字节相同；
仓库内产物必须与一次全新生成一致（由 `tests/test_replacement_coverage.py` 守住）。


## 后续 F07 检查点（2026-10-15）

本页原有数字和未覆盖项保留为历史检查点。现已完成有界 SpringSharp 3.0 工程迁移及本地验收，含 CLI、网页预览另存、混合炮组、估重采纳和规范备份恢复，见[迁移验收](sship-migration-2026-10-15.md)。真实用户旧文件和原生下载自动化仍有明确未确认边界；2.0/1.x 不支持。不能把 280 条文件参数处置换成 191 条功能等价覆盖率。
