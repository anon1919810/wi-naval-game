# 鱼雷空间 Implementation Plan

> Codex 审查／独立验收，OpenCode `opencode/deepseek-v4.1-flash-free` 实现。当前为计划。先独立读数，不修改现有经验空间评分。

**Goal:** 两条明确选择的鱼雷行产生量纲正确的甲板面积、舱内体积及各自比值。

**Architecture:** 新可选配置明确行范围与含凸舱船宽；纯核的 deck/hull 分支独立依赖，前端只读结果，旧质量模块保持原身份。

**Tech Stack:** 现有 Python／FastAPI／React／TypeScript，无新依赖。

**Spec:** `docs/superpowers/specs/2026-10-16-next-coverage-design.md` 的 C 节及公共约束。

## Global Constraints / Review Focus

- 不改变辅助武器质量、cost、结构／空间评分、质量建议、台账和源归档，不启用导入后的新假设。
- 水下源变量虽然叫 area，实际为体积；Task 1 对九种布置固定单位。
- count=0 是产品零占用政策；源旋转分支差异单列，不能记为原式一致。Task 1 固定政策边界。
- 8/3 必须保留源整数商；loads=0 的有效 1 不能写回原配置。Task 1 测试输入不变。
- 含凸舱宽不能从 hull.beam_m 或迁移归档自动确认；Task 2 测试缺值／矛盾。
- 只选两条、重复／失踪／非鱼雷引用拒绝；未选行不会进入比例。Task 2 测试明确范围。

## Task 1: 空间纯核和源输出

**Files:** Create `tools/plimsoll/auxiliary_space.py`, `tools/plimsoll/tests/test_auxiliary_space.py`, `tools/plimsoll/tests/fixtures/concept/original-auxiliary-space-vectors.json`。

**Consumes:** 既有辅助武器记录、独立 context 与新 config；原 50 条空间读数及其完整探针／船体上下文。

**Produces:** `validate_config(raw,auxiliary_records,path=...)` 和 `evaluate(records,context,config,path=...) -> dict`，method=`sps-3b3-auxiliary-space-v1`。结果至少 id=`selected_torpedoes`、records、values、availability、diagnostics、provenance；values 固定 `deck_area_m2,hull_volume_m3,deck_ratio,hull_ratio`，记录项 ID 为原 auxiliary ID。

- [ ] 先复用已有合适输出，仅补整数不能整除、零枚旋转分支、正分母／两行组合等缺口。源原名与正确量纲同时记录，原读数存在不等于独立对照通过。
- [ ] 按 source feet/inches 求值，再明确转 m²／m³。位置 0..3 活动为面积、另一占用为已知零，4..8 反之；位置未知正 count 两者未知。count=0 两者零且不读无关尺寸。
- [ ] 位置 1/2 正 count 才要求 loads；有效 loads 为 1（输入 0 时）或原正整数，超过 count 不可用，除法取整数。其余布置不依赖 loads。空引用集合是明确零占用，null 引用集合保持未知。
- [ ] 比值需要对应已知正分母，即使分子为零也不能把未知分母当 1。两支独立返回，未知 deck 不抹去已知 hull。所有输出 JSON 有限。
- [ ] 测试九布置、8/3、0组、超过枚数、零枚、null、未知位置、正负／非有限值、溢出与缺失分母。比较记录 source-domain 和 policy-guard，禁止把拒绝记相等。

## Task 2: 明确上下文及早期独立读数

**Files:** Modify `tools/plimsoll/concept_design.py`, `tools/plimsoll/verification.py`; create `tools/plimsoll/tests/test_auxiliary_space_workflow.py`。

**Consumes:** Task 1、hull canonical L/B/T/Cb、新声明 bulged_beam_m、既有版本水线面代理事实。

**Produces:** 可选 auxiliary_space 配置和 `design_balance.auxiliary_space`；methods 新族及当前源身份。

- [ ] torpedo_ids=null 或最多两个唯一合法引用；不同种类、失踪 ID 和重复结构化拒绝。删除仍被选中的鱼雷行须提示先解除引用，不静默选另一行。
- [ ] 含凸舱宽 nullable 0..1000 m，与已知规范宽的大小约束按 spec；输入普通来源，归档只作用户可查资料。长度、面积事实在 provenance 明确为声明或代理，不冒充实测几何。
- [ ] 不读取完整 hull_proxy 的无关 freeboard；deck_ratio 的水线面代理只读自己确需的既有事实。保存工程缺部分事实仍能得到独立已知占用。
- [ ] 无配置形状兼容；结果提前返回；旧质量 kernel 输出逐值不变，旧选中质量／cost／空间评分／强度评分不变；输入、原 `.sship` 和凭据不变。
- [ ] 阶段批次（仓库根目录，PYTHONUTF8=1、PYTHONPATH=tools;web/backend）：

```powershell
web/backend/.venv/Scripts/python.exe -B -m pytest tools/plimsoll/tests/test_auxiliary_space.py tools/plimsoll/tests/test_auxiliary_space_workflow.py tools/plimsoll/tests/test_auxiliary_weapons.py tools/plimsoll/tests/test_auxiliary_workflow.py tools/plimsoll/tests/test_additional_original_vectors.py -q
```

## Task 3: 普通配置、报告与方法比较

**Files:** Create `web/frontend/src/components/AuxiliarySpacePanel.tsx`, `web/frontend/src/__tests__/auxiliary-space.test.tsx`; modify `ConceptDesignEditor.tsx`, `conceptDesign.ts`, `AuxiliaryWeaponsEditor.tsx` 的引用删除提示、`ConceptComponentReadings.tsx`, `reportMetrics.ts`, `i18n/concept.ts`。

**Consumes:** 新声明与服务端结果，既有 ID／方法门限。

**Produces:** 独立开关、来源、两行明确选择、含凸舱宽输入；面积 m²、体积 m³和无量纲比例分别展示。

- [ ] 显示单行和所选范围，组数是 sets；不可用字段解释缺项，不在浏览器计算工程式，不提供质量采纳动作。
- [ ] 测试空／null 行选择、非鱼雷选项过滤、删除引用、单位显示、两支部分结果、未选行不计入、缺失／重复 ID 与版本冲突、完整报告父门限。
- [ ] 最终前端共享改动只做一次全量／build；统一真实浏览器／CLI 案例检查源归档和台账无变化，当前源码 quick 完成且 source identity 匹配。

## OpenCode brief

两个会话按核心／前端划定文件区域，显式 model 和绝对 directory，auto=true；保持 spec 与已有 50 条来源证据。回报实际命令、changed_files、比较样本／排除／政策边界以及未完成项。配额或费用变化停止 run；不改全局设置、旧方法或 Git 索引，不提交部署。
