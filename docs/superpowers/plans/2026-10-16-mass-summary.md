# 整炮组与装甲总重 Implementation Plan

> 执行方式遵循用户指定：Codex 定范围、审查和独立验收；OpenCode 使用 `opencode/deepseek-v4.1-flash-free` 实现。当前为计划，尚未启动实现。按阶段集中测试，不逐个小改动重复全量检查。

**Goal:** 给出来源整炮组与装甲总数，并与当前工况台账明确并列，不增加可采纳质量。

**Architecture:** 两个纯核接受既有布局结果和明确组成清单；`concept_design.py` 只作适配。新结果独立提前返回，前端读取服务端结果。

**Tech Stack:** Python／FastAPI／React／TypeScript，现有依赖。

**Spec:** `docs/superpowers/specs/2026-10-16-next-coverage-design.md`，以 A 节及公共约束为准。

## Global Constraints

- 保留当前未提交源码、旧原式向量和覆盖分母，不提交、推送或部署。
- 只读总数不生成质量模型，不改变已采纳质量、基本台账、其他工况、旧方法身份或旧建议。
- 缺失新配置时旧规范化结果和输出形状不变。完整报告保持 requested && completed 门限。
- 不从 update_proposals 合计估计；容差会让一些已知估计不出现在建议里。
- 只比较来源域内样本；不完整／越界／源异常分开计数，不许扩写为整舰准确率。

## Review Focus

- 两组不同每座门数时，按座数平均与按门数平均不同；只能用来源座数权重。
- 选择表已包含共享摇架 0.75，不能再次乘 shared_cradle；Task 1 固定该回归。
- 老布局两行身管倍径不同仍可使用旧能力，新整炮组总数不可用；Task 2 固定兼容行为。
- 缺少装甲声明与明确全覆盖零值不同；Task 2 检查小计、完整值及实际值互不替换。
- 同一个布局装甲不能与引用行 v1 再算；Task 2 加重复／已知近似／未知来源回归。

## Task 1: 整炮组纯核和来源证据

**Files:** Create `tools/plimsoll/battery_totals.py`, `tools/plimsoll/tests/test_battery_totals.py`, `tools/plimsoll/tests/fixtures/concept/original-battery-totals-vectors.json`。源探针在聊天工作目录新建 helper／evidence 子目录，恢复 C# 和 exe 只读。

**Consumes:** 已验证 layout、batteries 与 `battery_layout.evaluate(layout,batteries)` 的 groups／armour 结果；`concept_estimates` 的公开枪身、年代、炮座与单位函数。

**Produces:** `evaluate(layout,batteries,layout_reading,path='$.concept_design.battery_layouts') -> dict`；method=`sps-3b3-battery-totals-v1`，至少 `id,status,values,diagnostics,provenance`。values 为 `guns_t,mounts_t,armour_t,total_t`（原式总数不含弹药）。实际台账数由 Task 2 单独适配，不传入原式纯核。

- [ ] 先核对旧布局探针是否已有完整枪身／炮座输出，只补缺少的控制分支。包含 .75/1 系数混合、奇数座、单空组、零组、不同每座门数、1 in／10 in 分支及已知矛盾。每行记录原方法完成与输出赋值，禁止复制 C# 源码进仓库。
- [ ] 实现纯核，复用原式函数；所有使用过的输入、两个组和加权系数保留 provenance。无关弹重改变不影响枪身／炮座。
- [ ] 针对性测试至少固定：组一 2 座共享双联、组二 1 座单联时，整体系数为 `(2*.75+1)/3`，不能使用 `.8` 或再乘 `.75`；以及未知装甲只阻断总数、不抹去枪身与炮座。
- [ ] 阶段末运行 `test_battery_totals.py` 与旧 `test_battery_layout.py`／`test_concept_estimates.py`，保留实际输出。原对照容差 1e-5；每个政策拒绝另记，不计为数值相等。

## Task 2: 装甲汇总和所选台账适配

**Files:** Create `tools/plimsoll/armour_totals.py`, `tools/plimsoll/tests/test_armour_totals.py`, `tools/plimsoll/tests/test_mass_summary_workflow.py`; modify `tools/plimsoll/concept_design.py`, `tools/plimsoll/verification.py`。

**Consumes:** Task 1；已保存声明、既有 fixed/layout/v1 装甲内核结果、所选 effective_items 和角色解析。旧 `battery_layout.py` 与原方法不改算法。

**Produces:** 可选 mass_summary 校验；`armour_totals.evaluate(components, selected_roles, *, declared_complete, source, path=...) -> dict`；method=`sps-3b3-armour-totals-v1`。`selected_roles` 含九个角色的 t/null 及 `classification_complete`，components 每条含 `id,kind,target_id,method_version,mass_t`。

- [ ] 加 mass_summary 可选配置，按 spec 保留未知／缺失行为。列入所有声明组成，包括 mass_t=null 的项；来源向量中没有的质量不能取台账值补齐。
- [ ] 三带只取 main/ends/upper；全数按九角色边界计一次。已声明估计与实际所选质量分别得到结果；未确认完整范围只给明确标为小计的读数。
- [ ] `design_balance.battery_totals[]` 每项加 `selected_values`，字段与原式估计相同；按目标 ID 收集枪身／炮座／装甲，排除弹药。缺失／未知一项不得用估计替代。`armour_totals` 固定 id=`ship_armour`。
- [ ] 结果必须在旧 hull／balance 早退前提供；新 methods 族和 source identity 明确登记。既有请求版本、质量凭据和旧结果族不变。
- [ ] 新测试覆盖：无配置兼容；未知／空角色；未分类质量；完整范围 null/false/true；同目标去重／矛盾拒绝；删除声明后旧台账仍保留；估计落在建议容差内仍计入；旧 v1/v2 不重复；不同身管倍径只影响新读数。
- [ ] 阶段相关命令（仓库根目录）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='tools;web/backend'
web/backend/.venv/Scripts/python.exe -B -m pytest tools/plimsoll/tests/test_battery_totals.py tools/plimsoll/tests/test_armour_totals.py tools/plimsoll/tests/test_mass_summary_workflow.py tools/plimsoll/tests/test_battery_layout.py tools/plimsoll/tests/test_battery_layout_workflow.py tools/plimsoll/tests/test_concept_estimates.py -q
```

## Task 3: 普通表单、结果和比较

**Files:** Create `web/frontend/src/components/MassSummaryPanel.tsx`, `web/frontend/src/__tests__/mass-summary.test.tsx`; modify `ConceptDesignEditor.tsx`, `ConceptComponentReadings.tsx`, `conceptDesign.ts`, `reportMetrics.ts`, `i18n/concept.ts`，必要时仅在既有结果连接处改 `Workbench.tsx`。

**Consumes:** mass_summary 配置；两个新 family 的服务端结果和方法身份。

**Produces:** 开关／来源／完整范围确认，分列“当前工况”和“声明估计”，未完整项及不含弹药说明；保存报告和 ID／双层方法门限比较。

- [ ] 原式计算全部留在后端。面板不得出现新质量采纳按钮。
- [ ] 用返回值 fixture 测试：空白／部分结果、声明完整范围的含义、装甲带排除舱壁、弹药不入整炮组总数、重复／缺失 ID 和方法不匹配、父阶段未完成、不同显示质量单位。
- [ ] 本单元只跑相关前端测试；完整 suite/build 留到三单元合并后。独立验收不接受 OpenCode 自报通过。

## OpenCode brief 与验收交接

核心会话 directory=仓库绝对路径，model=`opencode/deepseek-v4.1-flash-free`，auto=true。只写 tools/plimsoll 及本单元新证据目录，先读 spec 和本计划；不改前端、旧证据、Git 索引或原程序集。前端会话 directory=仓库 `web/frontend` 绝对路径，接口确认后才发 brief；只写 src 下列明文件。

每次回报 changed_files、具体差异、执行命令／日志、源样本排除、未完成项。出现非零费用或配额失败停止该 run，不能自动换模型。两次实际返工失败后由 Codex 重新定范围。任务结束不提交；最终相关后端、真实浏览器／CLI、源码 quick 按总 spec 统一验收。
