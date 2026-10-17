# 炮位布局与混合装甲契约（2026-10-16）

本轮承接 F04。目标是保存两组炮架身份，由声明的分段干舷和布局计算炮位干舷、
高度系数，生成一个完整炮组的装甲建议。原有单列 v1 和火炮/炮座/弹药适配方法保留。
这不是型线、CG、射界、碰撞、实船装甲展开面积或完整 SPS 事件链求解。

## 数据边界

在 `concept_design` 新增可选数组 `battery_layouts`，缺省等价于未启用。
独立模块 `tools/plimsoll/battery_layout.py` 负责验证布局、数值推导及混合装甲，
`concept_design.py` 只负责系统/条目归属、角色与建议注册。

每条布局包含：

```json
{
  "id": "main_layout",
  "source": "declared synthetic layout",
  "group1": {
    "battery_id": "main_g1", "mount_selector": 4, "layout_index": 1,
    "elevated_mounts": 1, "deck_mounts": 1, "depressed_mounts": 0
  },
  "group2": {
    "battery_id": "main_g2", "mount_selector": 7, "layout_index": 7,
    "elevated_mounts": 0, "deck_mounts": 1, "depressed_mounts": 0
  },
  "group2_double_elevation": false,
  "group2_double_depression": false,
  "deck_profile": {
    "forecastle_fraction": 0.2, "forward_deck_fraction": 0.3,
    "forward_fore_m": 7, "forward_aft_m": 5,
    "aft_fore_m": 5, "aft_aft_m": 4
  },
  "armour": {
    "system_id": "weapons.main", "item_id": "main_layout_armour",
    "face_mm": 150, "rear_roof_mm": 100, "barbette_mm": 75
  }
}
```

- `group1`、`group2` 和 `armour` 可为 null；也可保存未完成组声明。null 组表示该组未配置，
  两组都未配置则布局不可用（不是已知零）。组内数值 null 为未知，0 为已知零。
- 布局最多 50 条；id 为 1..80 个 ASCII 字母、数字、下划线、点或连字符，且全局唯一。
  每项层数和每组座数不超过 1000，两组总座数不超过 1000，总炮管不超过 10000。
- 每组引用现有 `batteries` 中的一行，从该行读取口径、年代、炮型、炮座型、座数、
  每座门数和共用炮架。两组共同使用的口径、年代、炮型、炮座型必须一致；
  同时已知但矛盾时拒绝，缺值时允许草稿并返回不可用。
- `mount_selector` 使用恢复的 0..14 整数表，必须与被引用行的每座门数和共用炮架一致。
  该选择保留双列等不同结构的身份，不能只从门数倒推。
- `layout_index` 使用恢复的 0..17 整数表；18/None 不推断为任一布局。
- elevated/deck/depressed 为非负整数，合计必须等于该行座数；已知矛盾拒绝，缺值不补差。
- 不允许同一行被两个布局重复引用，或一条布局两次引用同一行。
- null 组及已知零座数的组不要求无关的选择器、布局、公共参数或双层标志。
  两组均为已知零时返回确定的干舷 0、高度系数 1，已启用装甲为零；不继承源码的旧状态。
  未选择 battery_id 的草稿不等于已知零，仍为不可用。所有显式提供的值仍检查类型/范围。
- 两个分段长度为 0..1 的比例，和不得超过 1；四个干舷为有限非负米值。
  这是经验甲板参数，不创建船体几何。双重高度标志为布尔或未知，不能把未知变成 false。
- 布局装甲有独立唯一目标，角色为 `gun_mount_armour`；与本布局各行的 v1 armour 互斥，
  防止同一炮组装甲以两个模型计重。所有归属/重复目标规则与现有概念模型一致。
- 删除已引用炮组前，网页必须提示并阻止或同时显式清除相关布局引用；不得生成悬空引用。

## 数学与来源

来源为原程序集 SHA256
`82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc`，
恢复文件 `GunControl.cs` 的 mountsCalc、perMountCalc、freeGunCalc、layoutCalc、
armWeightCalc、diameterCalc，以及 FreeboardControl.cs 的分段中点计算。

- 布局版本 `sps-3b3-battery-layout-v1`；混合装甲版本 `sps-3b3-battery-armour-v2`。
- 保持源码 `Math.Round` 的中点取偶数、0.5 分界，以及组间按**座数**加权干舷。
  高度项按炮管数计入高/低层并使用 group2 双层标志；不以座数替代炮管数。
- 混合装甲同时读取两组直径和座数；炮座筒项按源码整数除法计算平均每座门数，
  保留源码 mountAdj<=0.5 分支未对 perMounts 截顶的行为，不偷偷修正原算法。
- 炮罩高度、日期因子、英尺/英寸/长吨换算沿用已审查的来源。
  源码中的位置比例只作为带明示口径的布局读数，不填 x/y/KG。
- 非有限结果、零除和负装甲分量不得生成建议；返回结构化不可用诊断，不夹紧或编造最小值。
  零座数、零厚度和未知应分别测试，未知依赖不得使不相关的旧部件估重消失。
- v2 是完整两组装甲；现有逐组炮身/炮座/弹药仍是 `sps-3b3-adapted-v1`，
  不据此宣称原程序混合炮座总重量或整条事件链等价。

## 接口与接入

`battery_layout.validate_layouts(raw, batteries, path="$.concept_design.battery_layouts")`
返回规范布局列表；类型/范围/引用矛盾抛出带 diagnostics 的 ValueError 子类。
系统/条目归属与角色检查仍在 concept_design 内进行。

`battery_layout.evaluate(layout, batteries, path="$.concept_design.battery_layouts")`
返回 JSON 可序列化字典，至少含 `id`, `method_version`, `status`, `groups`,
`freeboard_m`, `super_factor`, `armour`, `diagnostics`, `provenance`。
未知字段返回 null；无装甲声明仍可计算布局。armour 使用与 v1 相同的
`values.total_long_tons` / face / rear_roof / barbette 分解与 provenance 结构。

- `generated_models` 在 hull_proxy 之前独立生成 `concept_layout.<id>.armour`。
  有限 LT→kg→t 边界复核后才注册，仍经现有原子审阅采纳和过期建议保护。
- `design_balance` 有配置时增加 `battery_layouts` 结果，即使经验平衡或物理型线缺失
  也保留能计算的布局读数。未配置时不改变原有结果结构和数值。
- 来源必须含布局声明、分组事实和独立方法版本；不直接采用质量、不推断 CG，
  不改基本账本或其他工况，也不自动覆盖已采纳质量。
- 既有采纳凭据的 inputs 为平坦标量。完整布局和组事实以允许的 `origin` 来源文本
  保存规范 JSON；未被读取的未知标量省略，完整声明中的 null 保留，不能用零替代。
- 验证器的源码身份包含新模块。

## .sship 3.0 与网页

- 新导入不再合并两条活动的同型组，保留 g1/g2 身份和独立估重目标。
  原有用户 JSON 不迁改。仅在组事实可支持时创建引用布局；不支持的原文继续归档并诊断。
- 使用权威的后部重复计数块；group1 deck 为来源总座数减其余五项，
  只在所有项已知且一致时计算。高度标志使用 159+bank / 174+bank；
  甲板比例 26/23 为百分数，干舷 27/25/24/22 按 hull 显示单位转为米。
- 布局原始值和自动推导值分开保存/显示。本轮迁移固定生成 `armour: null`；
  原装甲厚度保留现有精确归档/声明事实及待启用诊断，由用户在普通表单中选择独立目标后启用。
  不把炮塔厚度猜成完整分量，也不自动新增或采纳装甲质量。
- 普通表单支持新增/移除布局、选择两组、布局/层数、四段干舷和双层标志、
  独立装甲目标与厚度，中英标签和米/英尺显示。厚度规范保存 mm，干舷 m。
- 自动读数由服务器返回，网页不复制公式；修改后必须保存重算。

## 验收计划

1. 先保存原程序集对照样本和旧方法读数，记录调用完整性和失败阶段。
2. OpenCode 按先红后绿实现新模块及核心接入，核心定向测试由 Codex 独立重跑。
3. 按有界任务委派迁移和前端，保持各自会话上下文，禁止无关重构、新依赖、提交、推送和部署；连续两次未通过审查的内核由 Codex 接回修复并独立复核。
4. 原程序全布局/取偶数/非平甲板/混合选择/双层/零座数边界，与独立性质检查都通过。
5. 旧 v1 固定读数不变；草稿缺项、矛盾、数值溢出、目标重复和采纳防护回归通过。
6. 真实 API/worker 和浏览器验证修改→保存→建议→显式采纳→重算→重开，保留来源；
   同时确认基本质量、其他工况和过期建议防护。
7. 核心、后端相关测试，前端全套和构建，必要的最终源码身份检查通过后交付。

固定装甲区域是后续独立增量，不包含在本轮实现中。冻结 191 条观察清单不改写为已验证。
