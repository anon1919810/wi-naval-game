# 固定装甲、辅助武器与尺寸审阅契约

这些是可选的概念设计增量，沿用 `plimsoll-concept-design-1`。旧工程不自动加入新声明；没有启用的功能也不增加空结果章节。以下方法均为来源明确的经验段，不替代物理静水力、CG、GZ 或结构认证。

## 一项估重对应一个台账目标

`concept_design.fixed_armour` 与 `auxiliary_weapons` 各允许最多 50 条声明。每条有独立 `id`，为 1–80 个 ASCII 字母、数字、下划线、点或连字符；并有 `kind`、`system_id`、`item_id`、`source`。未完成草稿允许工程字段、类型或绑定为 null。非对象、非法类型、非有限数、超域值、重复 ID、重复目标和归属不符会产生结构化校验错误。

`item_id` 必须已经属于所选系统叶节点。全局目标唯一性同时覆盖火炮、炮座、弹药、单组装甲、两组布局装甲、机械、燃料、固定装甲、辅助武器及可调结构。删除声明不删除台账条目，也不撤销已经采纳的工况覆盖。

新部件使用既有 `replace_weight_item_mass` 建议和显式采纳入口。不会由填写字段、导入或重算自动替换质量。凭据保留独立方法版本、源程序集 SHA、公式、规范输入和完整声明／上下文 JSON 文本；没有扩展现有凭据的扁平输入合同。

## 固定装甲

方法 `sps-3b3-fixed-armour-v1`；生成模型 `concept_fixed_armour.<id>`。模块为 `tools/plimsoll/fixed_armour.py`，公开 `validate_configs`、`evaluate` 与 `ArmourValidationError`。

| kind | 工程字段 | 台账角色 |
| --- | --- | --- |
| `belt_main` | `thickness_mm`、`length_m`、`height_m` | `belt_main` |
| `belt_ends` | 同上 | `belt_ends` |
| `belt_upper` | 同上 | `belt_upper` |
| `bulkhead` | 同上 | `bulkhead` |
| `bulge` | 同上 | `armour_bulge` |
| `deck` | `thickness_mm`、`coverage_index`、`forecastle_fraction`、`quarterdeck_fraction`、`forecastle_mm`、`quarterdeck_mm` | `armour_deck` |
| `conning` | `thickness_mm`（前塔）、`aft_mm` | `conning` |

厚度为 0–2000 mm，长度为 0–5000 m，高度为 0–100 m。甲板覆盖选择为整数 0–6；两端长度比例为 0–1，已知时总和不超过 1。主／上装甲带的渐缩项读取声明船长、船宽和恢复的水线面系数；简单平板与指挥塔不被无关的干舷、艉型、轴数缺项阻断。

七种甲板选择中，0–3 沿用原式相同的中央面积基础；4–6 分别为机械舱、弹药库及两者的箱式中央面积。**所有选择都保留艏楼与后甲板分量。** 已确定为零的中央厚度不需要箱式载荷；已确定为零的两端面积不需要其厚度或水线面系数。未知的有效分量不是零。中央面积为负时，不能靠正的两端重量抵消成一个可采纳总重。

输出 `design_balance.fixed_armour[]`，每条带 ID、kind、方法、可用状态、数值、诊断、来源和 origin 文本。`values.total_long_tons` 与 `mass_t` 是同一完整质量的两种单位；甲板和指挥塔另有分量，不能把完整质量与分量再相加。几何量没有据此生成实际钢板、塔体或重心。

## 辅助武器

方法 `sps-3b3-auxiliary-weapons-v1`；模型 `concept_auxiliary.<id>`。模块 `auxiliary_weapons.py` 公开 `validate_configs`、`evaluate`、`AuxiliaryValidationError`。合并器材与装置重量的目标使用角色 `other`，不冒充裸炮、炮弹或新的强度／空间项。

| kind | 共同计数与布置 | 专有字段 |
| --- | --- | --- |
| `torpedo` | `count`、`loads`（组数）、`location_index` 0–8 | `diameter_mm`、`length_m` |
| `mine` | `count`、`loads`（备弹数）、`location_index` 0–3 | `unit_mass_kg` |
| `depth_charge` | 同上，含深弹架、投射器与两类反潜迫击炮 | `unit_mass_kg` |

计数须为 0–1000000 的整数；直径 0–2000 mm，长度 0–100 m，单具完整质量 0–100000 kg。鱼雷正质量读取声明舰体年代，项目年代域继续为 1850–1950；纯内核还对其更宽的受控年代域单独校验。

鱼雷组数不乘入重量；原程序只在说明和面积计算中使用它，并在面积路径把零组数内部改为一。本实现保留用户的零值，不改写规范声明。水雷／深弹将备弹数加到装载数，再乘完整单具质量；不能填入炸药量。器材已知为零时可不依赖位置；正器材质量而位置未知时，合计估重不可用。

输出 `design_balance.auxiliary_weapons[]`。`weapon_long_tons` 是原武器行显示的**不含装置**重量，`mount_long_tons` 是装置重量，`total_long_tons`／`mass_t` 才是单个目标的建议合计。这一区分也适用于旧观察清单中名字含“Total weight”的武器行，不能凭标签把它映射到合并总重。

鱼雷与水雷／深弹互换时，保留 ID、来源、绑定及装载数；组数／备弹数、布置与不适用几何清空待填。水雷与深弹互换保留完整单件质量及备弹数，布置清空。

## 尺寸审阅与造价

`armour_review` 为 `{source, belt_inclination_deg}`，后者允许 null 或 -89 至 89 度。方法 `sps-3b3-armour-review-v1`，模块 `armour_review.py`。不生成质量模型或采纳操作。

它逐项显示主带标准长度比、主带与端带总长、高度门限及经验最小主带长度。主／端带共用声明倾角；上带、凸舱及舱壁各用原规则。主／端总长对照要求两种各有唯一记录，不能任取第一条。经验最小长度只读取已返回的空间比和当前综合强度至少 0.5 的结果；未知、歧义或门限以下保持不可用。输出 `design_balance.armour_review`，`checks[]` 有稳定 ID、对应记录 ID、`pass/warning/unavailable`、数值及原因。告警不更改估重，也不替用户决定设计是否可接受。

`cost` 为 `{source}` 或 null，方法 `sps-3b3-cost-v1`，模块 `concept_cost.py`。它读取目标排水量、年代及**所选工况已存在**的机械、弹药、燃料和裸炮承载质量。未采纳建议、其他工况、未知或未绑定的炮重都不能替作零输入。装甲与辅助武器不是原式的直接成本项。负空船基础或非有限计算不可用。

结果 `design_balance.cost.values` 提供原 SPS 标签的百万美元／百万英镑、固定 4:1 比值、年份系数与三个来源分项。没有现代汇率、通胀调整或市场预算含义。

## `.sship` 与报告

仅限既有受支持的 SpringSharp 3.0 格式。固定装甲按装甲页自身尺度转换；五行辅助武器各用自己的尺度，不借用第一行或船体的选择。原始字节、各行文本、备注和单位索引保持归档。恢复的 190–197 位置实际对应 `dcControl1/2`；旧注册表 `deck_gun*` 名字保留，通过来源别名解释，不改写历史。

新导入事务性建立独立的未知质量目标及归属。支持的声明继续可编辑；超域字段留在归档并给出诊断。导入不会启用造价、设计平衡假设或自动采纳。倾角 201 只有在允许域内才进入尺寸审阅。

工作台独立展示可用部件；完整报告保持“已请求且阶段完成”的门限。比较按唯一记录 ID 对齐，要求记录与阶段都声明相同部件方法；不可用、缺失／重复 ID、缺失／冲突方法均不给数值差。长吨和来源货币维持原单位，最小长度按规范米保存。JSON／CSV 为完整规范结果和状态的无损序列化，不能把其中保留的不可用阶段原始证据当成可用报告读数。

实际对照、统一验收和未覆盖项见[本轮记录](coverage-marathon-2026-10-16.md)，日常步骤见[连续审阅流程](fixed-armour-cost-workflow.md)。
