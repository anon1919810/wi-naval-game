# 下一轮：总重审阅、装甲尺寸建议与鱼雷空间

日期：2026-10-16（北京时间）。状态：设计稿，未实施。延续上一轮本地验收，不提交、推送或部署；原代码、冻结 191 条清单、旧探针和验收文件均保留。

实施计划：[整炮组与装甲总重](../plans/2026-10-16-mass-summary.md) · [默认装甲尺寸](../plans/2026-10-16-armour-defaults.md) · [鱼雷空间](../plans/2026-10-16-auxiliary-space.md)。

## 意图与交付

下一轮把现有部件估重扩为可解释的整炮组／装甲总数，减少七类固定装甲的重复填写，并补上鱼雷组数真正影响的空间读数。推荐实施顺序为：**总重 → 默认装甲尺寸 → 鱼雷空间**。默认尺寸比原待办提前，是本次设计的选择，直接回应用户希望装甲覆盖更完整；空间另作独立单元，避免连带改变现有平衡评分。

按约 3 小时规划，阶段统一验收。三个单元可分别接受；进度或来源证据不足时如实保留未完成状态，不能为达到时长重复通过的测试，也不能因预算将未验收能力标为完成。

| 单元 | 用户可见成果 | 核心边界 |
| --- | --- | --- |
| A 总重审阅 | 同时看整炮组来源估计与当前台账；分清三条装甲带、全装甲、炮座、弹药 | 新结果只读，不产生第二份质量或整炮组分摊建议 |
| B 默认尺寸 | 预览八个默认维度，明确选择目标和字段，一次填入草稿 | 不填厚度，不改变已采纳质量；采用舍入前的规范建议 |
| C 鱼雷空间 | 九种布置的甲板面积／舱内容积与各自比值 | 不推导射界、CG、实体空间，不改变旧空间／强度评分 |

真实用户 `.sship` 尚未提供，实船校准继续作为后续工作；本轮不以等待文件作为阻塞项。

## 当前基础与来源

上一轮验收见 `docs/plimsoll-1.0/coverage-marathon-2026-10-16.md`，机器记录为同目录 `evidence/coverage-marathon-2026-10-16.json`。既有固定装甲、辅助武器质量、炮位与炮座装甲方法身份不变；现有凭据与所选工况采纳机制继续使用。

七项来源审计见 `evidence/coverage-remaining-source-audit-2026-10-16.json`。源程序集 SHA256 为 `82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc`。恢复 C# 只在本机只读，仓库仅保存独立实现及受控输入／输出。

已有 50 条鱼雷空间源读数可复用：聊天交付目录 `outputs/Plimsoll-coverage-marathon-2026-10-16/auxiliary-space-source-readiness.json`。它们不是已实现证据，不计入上一轮 862 个已对照读数；源探针的 `area_sqft` 名字在水下分支量纲错误，原值与正确量纲须同时保留。

## 可选声明与兼容

保留 `plimsoll-concept-design-1`，增加三个可选键。键缺失或 null 时不增加该结果族，旧规范化结果与默认请求行为不变。对象可保存未知草稿；错误类型、非有限数、越界、重复引用和已知矛盾结构化拒绝。

```json
{
  "mass_summary": {"source": null, "armour_scope_complete": null},
  "armour_defaults": {
    "source": null, "forecastle_fraction": null, "quarterdeck_fraction": null
  },
  "auxiliary_space": {
    "source": null, "torpedo_ids": null, "bulged_beam_m": null
  }
}
```

`source` 沿用现有来源文本规则。`armour_scope_complete` 为 null/boolean；只有 true 才明确声明未出现的装甲类别为零、所有声明共同构成完整估重范围。提示文案必须解释这一含义。false/null 允许显示已知小计，但不把它称为全舰总数。

默认尺寸的两个比例为 0..1，已知时总和不超过 1。空间的 `torpedo_ids` 为 null 或至多两个互不重复的既有辅助武器 ID，引用类型必须为 torpedo；null 是未声明，空数组是明确选择没有鱼雷。比值仅适用于这些明确选择的行，不把未选行默认为零。`bulged_beam_m` 为 null 或 0..1000 m，计算要求正数；与已知规范船宽矛盾（小于船宽）时拒绝。它有自己的来源，不从迁移归档自动确认，也不修改规范 `hull.beam_m`。

新增功能不会在 `.sship` 导入时自动启用。旧归档、五行器材、七类装甲、混合炮组身份和未知质量目标原样保留。

## A. 整炮组与装甲汇总

新增 `battery_totals.py`，方法 `sps-3b3-battery-totals-v1`。公开接口 `evaluate(layout, batteries, layout_reading, path=...) -> dict`；使用现有 `battery_layout.evaluate` 返回的 groups/mounts/barrels/armour，不重写旧布局内核。

活动组共同事实须已知且相同：口径、身管倍径、年代、炮种、炮座类型。旧布局允许不同身管倍径的工程仍可打开并使用旧装甲模型，新整炮组读数应不可用，而非拒绝整个旧工程。无活动组的未知与明确零组沿用旧布局区别。

枪身质量复用 `concept_estimates.gun_mass_long_tons`，安装门数为两组之和。整炮座用 `mount_mass_long_tons` 和按座数加权的 `weight_adjustment`，传入 `shared_cradle=False`，防止选择表的 0.75 再乘一次。手动炮弹重量不参与枪身公式。源整炮组总数为枪身＋炮座＋当前布局完整装甲，不含弹药；装甲未知则这项总数未知，但已知枪身／炮座继续可读。

同时在 `selected_values` 返回当前选择工况中引用行的枪身／炮座／装甲目标质量之和，键同为 guns_t/mounts_t/armour_t/total_t，按叶项 ID 去重且排除弹药；未知目标或来源边界不完整时未知。零质量有效。实际质量与来源估计分别命名，不作替代。此轮不分配全炮组估计到两行，不生成新模型和采纳建议，也不删除旧行建议。

新增 `armour_totals.py`，方法 `sps-3b3-armour-totals-v1`。公开接口：
`evaluate(components, selected_roles, *, declared_complete, source, path=...) -> dict`。
components 是适配层提供的所有已声明装甲项（`id, kind, target_id, method_version, mass_t`）；id 使用 fixed:/layout:/battery: 命名空间，避免不同族的相同局部 ID 被误去重。未知项必须保留为 mass_t=null，不能只收集成功项或 update_proposals。布局覆盖的旧 v1 装甲不再加入；旋转装甲与炮座筒各计一次。未知绑定不能被猜成新目标。

三带仅为 main/ends/upper；全装甲再加 bulkhead/bulge/deck/conning 与枪炮装甲。selected_roles 为现有九个 `ARMOUR_ROLES` 的规范吨质量，外加 `classification_complete` 标志；使用现有角色归属，未分类质量或任一未知所需角色使实际全数未知。已有角色空集合的显式零规则不变。

输出固定字段 `estimated_belts_t, estimated_total_t, selected_belts_t, selected_total_t, known_estimate_subtotal_t`。估计完整范围未确认或任一组成未知时，前两项对应的完整值为 null，小计注明未覆盖项。部件估计存在但超出建议比较容差、尚未绑定或已经采纳，不影响其被列入声明估计；绝不从建议列表推断完整总重。

结果放在 `design_balance.battery_totals[]`（ID=layout ID）、`design_balance.armour_totals`（稳定 ID=`ship_armour`）。质量显示可随现有偏好，规范值为 t，来源原式长吨另保留在 provenance。

## B. 默认装甲尺寸建议

新增 `armour_defaults.py`，方法 `sps-3b3-armour-defaults-v1`。公开接口 `validate_config(raw, path=...)` 与 `evaluate(config, context, path=...) -> dict`。context 仅需 `length_m, beam_m, draught_m, block_coeff, freeboard_m`，不借用艉型、轴数或载荷。

原式在 ft 中求值再转 m；不能把带平方根的经验式直接换成米。侧吃水采用 `HullControl.cs:1246`，主高取 `min(1.2*sqrt(beam_ft), side_draught_ft+freeboard_ft)`；主长 `(1-fc-qd)*L`，端长 `L-main-.02 ft`，上高 `min(8 ft,freeboard)`，舱壁高为侧吃水。返回主／端／上／舱壁的八个维度。非正方形系数、负结果、溢出只阻断相关字段；不钳制为零，不使独立已知长度失效。

明确采用**原式舍入前的规范建议**，不复刻源按钮 N2 文本的英制／公制量化。向量记录原对象的 Est 字段及其自身单位，显示两位小数不改变规范建议。预览带方法、输入和精度边界。八个 values 键为 main_length_m/main_height_m/ends_length_m/ends_height_m/upper_length_m/upper_height_m/bulkhead_length_m/bulkhead_height_m；availability 按相同键逐项给出状态／原因。超出现有 length_m 0..5000 m、height_m 0..100 m 域的建议不允许复制，不能靠前端保存错误代替预览诊断。

前端 `ArmourDefaultsPanel.tsx` 读取当前已保存结果。用户明确选择既有固定装甲记录及要填写的 length_m/height_m；多个同类记录逐项选择，端／上／舱壁按对应字段映射。不能给甲板、指挥塔或凸舱套用无来源默认尺寸。

应用仅一次性更新本地草稿，保留记录 ID、kind、目标、厚度及已有来源文本，并追加一次方法／来源运行 ID 注记。原来源不能被覆盖或静默截断；该注记是普通声明，不冒充服务端质量采纳凭据。尚未保存的草稿、项目修订／工况／请求／运行不符时不能复制旧建议；复制后旧建议失效。资格检查不要求旧 mass proposals 非空或父 balance 完成，只要求当前身份匹配及所选新字段可用。取消不改工程；保存仍走普通修订接口，已采纳质量与其他工况不变。

输出 `design_balance.armour_defaults`，八个字段规范米、逐字段 availability、诊断和 provenance。没有质量模型／采纳操作。

## C. 鱼雷空间

新增 `auxiliary_space.py`，方法 `sps-3b3-auxiliary-space-v1`。公开接口 `validate_config(raw, auxiliary_records, path=...)`、`evaluate(records, context, config, path=...) -> dict`。context 为 `length_m, beam_m, draught_m, block_coeff, waterplane_area_m2`；含凸舱船宽只读本功能明确声明。

只计算所选两行鱼雷，复用已有 count/loads/diameter_mm/length_m/location_index。布置 0..3 返回面积 m²，4..8 返回体积 m³。两项汇总分别除水线面面积和 `L*bulged_beam*T*Cb`；不相加，不把名称为 area 的水下变量当平方量。

正 count 的布置 1/2 需要组数：0 在计算中有效值为 1，原输入保留；有效组数大于枚数时空间不可用。不能整除时保留原整数除法，例如 8/3 为 2。其他布置不依赖 loads。count=0 的产品范围明确返回零占用，不复制源旋转分支的正占用异常，并将其作为政策边界而非原式一致样本。

占用量已知为零不依赖无关尺寸；比值仍需已知正分母。未知分量不从总数中略去，deck/hull 两支独立可用。位置和所需事实缺失、非法类型、负数、溢出均有结构化诊断与有限 JSON。源单位、整数商、有效组数和政策边界保留在 provenance；面积／体积本轮固定显示 m²／m³，比例无量纲。

输出 `design_balance.auxiliary_space`：`records[]` 按 ID，values 为 `deck_area_m2, hull_volume_m3, deck_ratio, hull_ratio`，逐字段可用状态和来源输入。该 family 不改变 `auxiliary_weapons` 质量结果、自动机械估重、cost、原空间评分、结构评分、重量账本或 `.sship` 字节。

## 集成、报告和身份

三个单元从既有 `design_balance` 提前输出独立结果，不新增分析阶段。methods 按新结果族登记；请求版本和旧方法版本保持不变。独立组件在工作台可见，完整保存报告仍要求 requested && completed；JSON／CSV 保留原状态。

比较按稳定 ID 与阶段、记录双层方法身份，缺失／重复／冲突均阻断数值差。新纯核入 verification._source_identity。前端没有工程公式，不扩展凭据的扁平输入合同，也不在本轮加新服务端写端点。

## 实施分工和集中验收

用户已指定 OpenCode 实现。当前实测可用的模型为 `opencode/deepseek-v4.1-flash-free`：2026-10-16 的只读探针成功，cost=0、无工具调用／文件改动。服务声明 context=200000、output=32000。它证明当时连通与费用记录，不保证后续无限额度或实现质量。

采用两个有边界的 OpenCode 会话：核心／源证据与前端；都显式传 model 和绝对 directory，auto=true。一次交付一个单元，接口稳定后才交给前端；共享 `concept_design.py`／表单配置文件不由多个会话同时写。Codex 持有规格、原证据边界、独立验收和最终结论。出现配额／费用变化先停止该 run，不自动换付费模型或改全局设置；失败两轮后重新定范围。

计划时间：A 约 60–75 分钟，B 约 35–45 分钟，C 约 45–60 分钟，最终合并验收约 20–30 分钟。是顺序与容量估计，不是到点即通过。开发中只定位必要错误；阶段末一次相关核心／后端批次。前端最终全量和 build 各一次，交付前当前源码 quick 一次，旧大矩阵不反复执行。

统一浏览器案例：已审阅合成工程启用总数 → 修改一项声明观察估计变化而已采纳值不变 → 预览八维度并只填一项 → 保存重算／重开 → 切换空间两行和含凸舱船宽 → 检查报告与 ID 比较。旧源字节、基本账本、其他工况和旧质量凭据均保留。真实 CLI import/analyze/export 需覆盖新结果；partial 状态如实保留。

本轮设计不计入任何新增覆盖完成数。实施后分类追加对应原清单的证据，不能改冻结分母、用源读数存在冒充已比较、或把经验空间／默认尺寸宣称为物理设计验证。
