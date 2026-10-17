# 默认装甲尺寸 Implementation Plan

> Codex 设计／独立验收，OpenCode `opencode/deepseek-v4.1-flash-free` 实现；当前仅计划。继承用户集中验收要求，不逐字段跑全量测试。

**Goal:** 八个有来源的默认维度可预览、明确选择并写入草稿，保留已采纳质量。

**Architecture:** 独立纯核产生字段结果；普通概念配置开启它，专用面板将当前服务端建议复制到现有固定装甲字段。复用保存修订，无新写端点。

**Tech Stack:** Python／React／TypeScript，零新依赖。

**Spec:** `docs/superpowers/specs/2026-10-16-next-coverage-design.md` 的 B 节及公共约束。

## Global Constraints / Review Focus

- 不修改固定装甲估重、旧台账、单位保存语义、原始 `.sship` 或冻结清单，不自动导入启用或提交部署。
- 原式先按 ft 求值再转 m；默认主高读侧吃水而非正常吃水。Task 1 验证手算与原 Est 值。
- 采用舍入前建议，两个源尺度均记录正确归一化；不宣称源 N2 文本往返一致。Task 1 固定此边界。
- 草稿／修订／工况／请求改变使复制失效；Task 3 测试，不借旧建议覆盖新编辑。
- 多记录和不可用字段必须明确选择；任一选项非法时整批草稿不变。Task 2 覆盖原子性。

## Task 1: 纯核与有界原探针

**Files:** Create `tools/plimsoll/armour_defaults.py`, `tools/plimsoll/tests/test_armour_defaults.py`, `tools/plimsoll/tests/fixtures/concept/original-armour-defaults-vectors.json`。探针 helper／原始证据在聊天目录新建。

**Consumes:** 可选配置 source/fc/qd；context=`length_m,beam_m,draught_m,block_coeff,freeboard_m`。

**Produces:** `validate_config(raw,path=...) -> dict|None`；`evaluate(config,context,path=...) -> dict`，method=`sps-3b3-armour-defaults-v1`。values 键为 `main_length_m,main_height_m,ends_length_m,ends_height_m,upper_length_m,upper_height_m,bulkhead_length_m,bulkhead_height_m`；availability 为各键的状态／原因。

- [ ] 有界调用源 Default 按钮，记录原 Est 字段、scale、文本与完成状态。只把舍入前字段用于纯核对照，文本记录用于解释排除范围；原程序只读。
- [ ] 实现来源公式，字段独立依赖和有限 JSON。负端长、侧吃水非法或超出现有固定字段域的建议不能被复制；其他已知字段继续显示。
- [ ] 测试基本手算、fc+qd=0 时端长为负、fc+qd=1、未知 freeboard／Cb、Cb=0、正低 Cb 导致负侧吃水、源单位 0/1、极大有限数与非有限拒绝。长度可用而高度未知不能整项丢弃。
- [ ] 阶段相关测试：`web/backend/.venv/Scripts/python.exe -B -m pytest tools/plimsoll/tests/test_armour_defaults.py tools/plimsoll/tests/test_fixed_armour.py -q`，PYTHONPATH=tools。

## Task 2: 结果及纯草稿映射

**Files:** Modify `tools/plimsoll/concept_design.py`, `tools/plimsoll/verification.py`; create `tools/plimsoll/tests/test_armour_defaults_workflow.py`, `web/frontend/src/components/armourDefaults.ts`, `web/frontend/src/__tests__/armour-defaults.test.tsx`。

**Consumes:** Task 1；现有规范工程和保存运行。

**Produces:** `design_balance.armour_defaults`、新方法身份；前端纯函数 `applyArmourDefaults(config,preview,selections,sourceRunId) -> Raw`，selections 为 `{record_id,fields:('length_m'|'height_m')[]}[]`。

- [ ] 可选配置缺失兼容，早退前读取新纯核。未知或不合法输入沿用现有项目结构化校验，不借用 first deck/layout 的分段值。
- [ ] 映射按记录 kind 和八个固定结果键。仅允许 belt_main/belt_ends/belt_upper/bulkhead，拒绝重复、失踪 ID、非法 kind、选中的不可用／非有限／超域值。所有选择检查后一次返回新 config，任何失败不产生半批。
- [ ] 保留非所选字段、记录 ID、绑定、厚度和旧来源文本，追加一次方法与源运行 ID 注记；已有同注记不重复。注记不是重量采纳凭据，不能静默截断来源。
- [ ] 核心 workflow 检查保存重开、已采纳质量／基本台账／其他工况／旧凭据不变；后续重算可产生新估重建议，绝不自动采纳。

## Task 3: 预览和用户选择

**Files:** Create `web/frontend/src/components/ArmourDefaultsPanel.tsx`; modify `ConceptDesignEditor.tsx`, `FixedArmourEditor.tsx`, `ConceptComponentReadings.tsx`, `reportMetrics.ts`, `i18n/concept.ts`, `Workbench.tsx` 的必要传递处。

**Consumes:** 返回的八字段结果，当前运行身份，以及 Task 2 纯映射函数。

**Produces:** 明确的“预览尺寸建议”／“填入所选字段”交互，不使用“采纳重量”文案。

- [ ] 开关、来源和两个分段比例为普通表单。复制需要当前已保存运行及未修改草稿，revision/project/condition/request/run 任一不符都禁用并解释原因。复制后正常标记草稿已改、隐藏旧建议；保存仍由用户明确触发。
- [ ] 多同类记录逐项选择，展示精确规范值与显示值的区别；没有目标时提示添加声明，不自动创建台账或七条记录。
- [ ] 对返回 fixture 做 UI 测试：中文标签、单字段选择、混合多记录、取消、过期／脏草稿、feet 偏好不改规范值、不可用字段不能选、无质量采纳按钮、父报告门限。
- [ ] 运行本单元相关前端和核心 workflow 批次；前端全量与 build 仅最终合并后执行。

## OpenCode brief

先发核心／证据任务，再在已确认返回结构下发前端任务。沿用两个受限写入区域：tools/plimsoll 与 web/frontend/src。每次显式传 model／绝对 directory／auto=true；回报 changed_files、原探针对照、政策拒绝、实际命令和未完成项。禁止自动改付费模型、Git 索引、部署或旧来源证据。
