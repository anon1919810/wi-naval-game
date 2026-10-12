# Y’s Formfield / Plimsoll 全站改进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to track this plan. The user subsequently requested “不需要Opencode,你亲自来”; Codex now implements, reviews and accepts the remaining work directly. Preserve existing dirty work and use read-only final review when needed.

**Status:** 已完成本轮本地修复与验收；2026-10-12 用户追加授权提交、推送和公网发布。逐簇进度与证据见任务输出目录中的 `sitewide-improvement-2026-10-11/progress.md` 和 `acceptance.md`；发布状态见 [发布记录](../../formfield/release-sitewide-2026-10-12.md)。

**Goal:** 完成全站双语、项目操作效率、可读报告对照和损伤试验解释，并通过本地整体验收，使新用户能完成首次计算、研究差异及备份复核。

**Architecture:** 复用现有语言状态、项目/运行 API、不可变报告、诊断定位及 Three.js 检查器。增加薄的文案与报告指标映射、客户端检索和只读试验比较，不改变数值求解或存储契约。各任务交付可独立验收的完整功能簇。

**Tech Stack:** 当前 React / TypeScript / Vite / Three.js、Python / FastAPI 及现有存储；不新增基础框架。

**Spec:** [全站改进设计](../specs/2026-10-11-sitewide-improvement-design.md)。执行者先读设计，再读本计划；实施分工以用户最新的 Codex 直接编程要求为准。

**Repository:** `C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`。下列源码和测试路径相对此目录；npm 命令在其 `web/frontend` 运行。

**Evidence directory:** `C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/`。下列 `outputs/...` 指此任务输出目录，不指仓库中的同名路径。

## Global Constraints

- 首次默认英文，保留明确保存的语言偏好；右上角切换在所有应用页面可用。
- Space Grotesk / Inter、瑞士网格、蓝色预览/红点、手动主题及已确认音效保持。
- 不改变计算核算法、方法身份、项目和报告格式、冻结运行、规范单位、未知值语义与当前结果身份保护。
- 当前草稿、当前结果、历史运行与受控对照分别保持自己的身份，不让显示切换改变数据。
- 保留所有已有未提交工作，独立核心验证文件是保护区；先本地验收，不暂存、提交、推送或公网部署。
- Codex 按用户最新要求直接实现、审查与验收；不再向 OpenCode 委派本计划的后续实现。
- 不引入新账户、AI 服务、数据库迁移、计算模型或新报告格式。
- 采用现有技术栈。按簇测试，只有新失败、相关改动或明确风险才扩大回归。

## Review Focus

1. 切换语言或快速导航时，未保存草稿、活跃计算、Cookie 身份和实验室镜头不能被重置（任务 1、2、4）。
2. 旧修订、旧工况或旧请求的有效结果不能被显示为当前草稿结论；原始证据和导出不能随翻译改变（任务 1、3、4）。
3. 未知、真实零、取消/部分完成、方法差异和不同接受终点不能生成误导性的对照差值（任务 3、4）。
4. 后端离线、读取失败、重复点击、晚到响应和失效 Cookie 不能制造空项目库假象、重复项目或自动重放计算（任务 2、6）。
5. 中英文长文本、390px、键盘操作、减少动效和 WebGL 失败时仍能理解并完成操作；动画不能抢焦点或镜头（任务 5、6）。

## 顺序与交付边界

`0 基线 → 1 语言 → 2 操作 → 3 报告 → 4 实验室 → 5 全站整合 → 6 验收`

每簇完成并独立验收后进入下一簇；不把所有文件一并交给一个无边界长循环。任务 4 引入的新标签使用任务 1 的接口，任务 5 对最终页面做统一检查。一个簇若受外部条件阻塞，记录原因并继续无依赖工作；不能用测试通过冒充没有完成的人工验收。

### Task 0: 建立实际工作区基线

**Files / evidence:** `git status`、现有 `docs/formfield/CHANGELOG.md`、`docs/plimsoll-1.0/current-status.md`、上一轮 `outputs/capabilities-onboarding-2026-10-11/acceptance.md`；新记录放本地任务输出目录 `outputs/sitewide-improvement-2026-10-11/`。

**Consumes:** 当前工作区文件及既有本地服务。**Produces:** `baseline.json`（HEAD、文件状态/摘要、保护文件、服务地址）和 `acceptance.md`（本轮证据逐簇追加）。

- [ ] 核对工作区、当前运行服务及上一轮未提交成果，记录保护边界；已有语言/引导成果不能漏入基线。
- [ ] 记录当前路由请求与构建大小、桌面及窄屏关键页面；使用专用验收数据库/案例，避免污染其他任务。
- [ ] 为每簇记录可运行验收命令、允许修改文件、语义约束及不得提交部署的边界；原 OpenCode brief 保留作历史记录。

**Acceptance:** 基线列明本轮范围与并行保护区，源码尚未改变；本地服务可用或明确记录启动方式。

### Task 1: 贯通全站语言与术语

**Files:** `web/frontend/src/portfolio/{LanguageProvider.tsx,language.ts,Portfolio.tsx}`、`App.tsx`、`pages/{Library,Login,Workbench,Run,Report}.tsx`、相关 `components/`、`damageLab/` 及 `audio/SoundToggle.tsx`。新文案按需放 `src/i18n/{workspace,lab,terms}.ts`，保持路由加载边界。

**Interfaces:** 继续使用 `useLanguage(): LanguageApi`、`language: 'en' | 'zh-CN'` 和唯一的 `setLanguage`。工具和实验室使用各自类型化查词函数，参数插值规则与现有 `translate` 一致，不创建第二个偏好存储。核心返回记录不进入翻译写入流程。

- [ ] 先列出应用自有文本清单和原文例外，建立简短中英术语表；复用已有总站 205 对文案而非重建词典。
- [ ] 扩展工作空间右上角语言开关和文档 `lang`，覆盖工具、全部编辑章节、运行、报告/打印和实验室；已知诊断解释与原始诊断分层呈现。
- [ ] 确保语言是原地渲染变化，保持表单、身份、请求、滚动、镜头、回放、选中项、主题和静音；新增字符串同时写两个语言版本。
- [ ] 用一组针对性测试验证默认/保存偏好、字典键与插值、脏草稿和运行中切换；不为每条文案建立逐字快照。
- [ ] 独立检查全部可见界面文本，按页面出清单；原始数据/诊断/用户名称例外单列，不能靠中文字符扫描误改数据。

**Acceptance command:** 在 `web/frontend` 运行 `npm.cmd run test -- src/__tests__/language-switch.test.tsx src/__tests__/anonymous-workspace.test.tsx src/__tests__/workbench.test.tsx src/__tests__/leave-guard.test.tsx src/__tests__/run.test.tsx --maxWorkers=2`，再执行 `npm.cmd run build`。在这些既有测试中补语言状态关键断言；实验室状态断言纳入任务 4。

**Browser gate:** 中英往返总站→项目库→已编辑项目→运行→报告→实验室；未保存输入和活跃状态保持，首次默认 EN。

### Task 2: 项目检索、章节定位与操作反馈

**Files:** `pages/{Library,Workbench,Run}.tsx`、`components/{ProjectNav,WorkbenchOverview,CalculationReadiness,DiagnosticAction,ReadPending}.tsx`、`components/diagnosticGuidance.ts`、`styles/workspace.css` 及任务 1 文案文件。

**Interfaces:** 项目检索只消费既有项目列表；章节检索消费 `CHAPTERS` 并调用 `ProjectNav` 既有 `onSelect(chapter: Chapter)`，不变更章节 ID。诊断定位仍经过现有 `resolveDiagnosticLocation` 的快照/实时输入身份检查。

- [ ] 项目库增加按项目名过滤、结果数、清除条件；区别未加载、读取失败、真实空库和没有匹配；不增加逐项目详情请求。
- [ ] 章节索引增加中英文标题/关键词过滤，支持键盘选择与清除；切换章节保留输入，继续复用诊断直达具体字段。
- [ ] 整理工作头的修订、工况、脏状态、保存和运行说明；复用计算就绪视图解释请求范围和上次检查，保持默认请求不变。
- [ ] 在本簇页面统一加载、失败和重试反馈，检查重复点击/过期请求；只修复实际发现的问题，不重写已有 API 生命周期。
- [ ] 集中覆盖检索无匹配/清除、长中英文名称、脏草稿导航、失败保留数据、重复提交保护。

**Acceptance command:** `npm.cmd run test -- src/__tests__/anonymous-workspace.test.tsx src/__tests__/workbench-hierarchy.test.tsx src/__tests__/diagnostic-guidance.test.tsx src/__tests__/diagnostic-guidance-arrival.test.tsx src/__tests__/leave-guard.test.tsx src/__tests__/run.test.tsx --maxWorkers=2`，在既有文件中增加相关行为断言。

**Browser gate:** 从项目检索到定位章节、修改保存、运行、诊断返回输入；模拟一次 API 读取失败，重试不生成第二个项目。

### Task 3: 结果阅读与运行对照

**Files:** `pages/Report.tsx`、`components/{ReportReadings,FormResults,StageIndex,StageStatus,SourceInspector}.tsx`、`components/{resultReading,units}.ts`；创建 `components/reportComparison.ts`、`__tests__/report-comparison.test.ts`，使用任务 1 文案文件。

**Interfaces:** `compareReports(left: RunView, right: RunView)` 返回 `identity`、`inputChanges`、`groups`、`warnings`。指标由显式路径/维度注册表从已保存 `AnalysisResult` 读取；每格含 known/unknown/unrequested/incompatible 等展示状态、原始路径和可选数值，不把缺失值强制转数字。呈现层使用已有 `UnitProvider`；原始导出仍走原有 API。

- [ ] 建立固定的常用指标分组和中英名称，取消最多 8 项的对象遍历截断；超出注册表的数据保留原始阶段视图。
- [ ] 展示两个运行的身份、请求与方法差异；允许同项目跨修订研究对照，但清楚列出改变的输入，不声称受控因果。
- [ ] 对阶段状态、单位维度、方法及数值有效性逐项检查；未知/不适用独立显示，安全处理真实零与百分比差；差值方向统一标注为 B−A。
- [ ] 把已有读数、诊断行动与来源组织成先读结论、再看依据的层级；保留完整的原始结果入口和模型限制。
- [ ] 验证切换对照的晚到响应、取消/部分结果、不同修订/工况/方法、未知/零、显示单位；打印与网页身份一致，JSON/CSV 内容不受语言和单位选择影响。

**Acceptance command:** `npm.cmd run test -- src/__tests__/report-comparison.test.ts src/__tests__/report.test.tsx src/__tests__/report-print.test.tsx src/__tests__/report-navigation.test.tsx src/__tests__/result-reading.test.ts src/__tests__/display-units.test.tsx --maxWorkers=2`。

**Browser gate:** 使用同一项目两次冻结运行，修改修订后对照并打印；旧报告仍为旧修订。没有请求的 GZ/续航不出现伪差值。

### Task 4: 损伤预设、A/B 与证据解释

**Files:** `damageLab/{Page,Inspector,Detonation,Replay}.tsx`、`{types,narrative,model}.ts`、`lab.css`；新建 `{presets,comparison,consequences}.ts`、`Comparison.tsx` 及相应 `.test.ts`。具体数据路径以 [现有对照提案](2026-10-11-damage-lab-comparison.md) 为起点核对当前类型。

**Interfaces:**
- `buildPreset(project, baseline, preset): Experiment` 只产生新草稿，拒绝不兼容布局。
- `compareTrials(a: LabRun, b: LabRun)` 消费冻结记录，输出兼容性、输入变化和分组差值，不修改激活试验。
- `explainTarget(result: LabResult, frame: number, target: InspectionTarget)` 消费结构化路径/界面/事件，返回带来源 ID 的解释，不解析自由文本事件消息。

- [ ] 做三个合成预设并显示假设；只在用户明确运行后排队，通过已有预览/准入校验配置。
- [ ] 从已完成记录选 A/B；按设计检查修订、工况、方法、seed/数量/输入与接受终点，未知值不算零差；读取过期结果不能覆盖新选择。
- [ ] 区分机械、进水和人员因子及其乘法关系，再呈现综合可用性；分开水体积与水质量，不推导不存在的航速或生存结论。
- [ ] 把目标损伤与对应弹片路径、舱壁响应、生成孔和核心流量连接；前事件帧不泄露后续状态，多孔水量保持聚合标识。
- [ ] 新功能双语、可键盘操作；A/B 选择不改草稿、回放和镜头；查看旧试验遇修订不符给清晰原因。
- [ ] 集中验证遮挡/透过、未知人员/功率、旧记录、不同时间端点、过期 fetch、原始记录不变与起爆前状态。

**Acceptance command:** `npm.cmd run test -- src/damageLab --maxWorkers=2` 和 `npm.cmd run build`。仅在请求/后端集成发生实际改动时运行相应 Python 实验室簇，不改数值核则不例行跑核心全量。

**Browser gate:** 专用合成项目跑三预设、比较遮挡对并打开解释；核对无损模块、传播路径与核心接受的水量。回放推进仅高亮；点击定位才移动镜头。

### Task 5: 全站排版、可达性和实测性能

**Files:** `portfolio/{portfolio,content,pageGeometry}.css`、`styles/workspace.css`、`damageLab/{lab.css,Scene.tsx}`；`portfolio/Portfolio.tsx`、现有声音/加载/动效模块及 `vite.config.ts` 仅在实测需要时修改。

**Consumes:** 最终双语页面和基线证据。**Produces:** `visual-matrix.md`、`performance-before-after.json`、必要截图，以及最多三项有证据的性能改进。

- [ ] 对 Work/About/Credits/详情、项目库、工作台、运行、报告和实验室巡检，修复字号、列线、留白及操作区不一致；保留既有视觉语言。
- [ ] 在 390/768/1024/1440/1920 宽度检查长文本和控件；文档无横向溢出，表格局部滚动，三维检查文字仍可访问。
- [ ] 核对键盘可见焦点、深浅主题、减少动效、静音、WebGL 回退与资源失败恢复；切换页面无双响或尾音泄漏，不新增声音设计。
- [ ] 比较构建、公开首屏请求、工作空间首次进入、切换章节、长报告及实验室回放的同环境测量；从已测主要开销选择最多三项优化。
- [ ] 复核离屏/隐藏暂停、资源回收、懒加载；保留 nginx 既有正确压缩/缓存/404 配置，不因本地 Vite 行为误改生产模板。

**Acceptance command:** `npm.cmd run test -- src/__tests__/portfolio-transitions.test.tsx src/__tests__/reading-scroll.test.ts src/__tests__/workspace-motion.test.tsx src/__tests__/interaction-audio.test.ts src/__tests__/audio-warm-policy.test.ts src/__tests__/image-loading-policy.test.tsx src/damageLab/Scene.test.tsx --maxWorkers=2`；`npm.cmd run build`。与本簇无关的既有测试失败须解释，不反复扩大测试掩盖原因。

**Performance gate:** 相同环境/交互下提供前后数据；公开静态页不加载 Three.js，关闭音效不首屏全量加载 WAV，无持续累积的三维实例/监听器。新增功能导致体积变化写清归属，不以体积告警本身为失败。

### Task 6: 交叉验收与本地交付

**Files / outputs:** 本轮 `acceptance.md`、文字清单、截图、性能对照、文件保护检查；可在 `docs/formfield/` 新增本轮交接，并以“仅本地”记录状态。

- [ ] 首次访问 EN → 切换中文 → 案例创建 → 保存 → 首次运行 → 读报告/导出；另一语言重走关键入口。
- [ ] 修改项目形成新修订 → 第二次运行 → 报告对照 → 重开旧报告，验证新旧身份和未知语义。
- [ ] 下载项目备份 → 恢复为新项目；确认报告 JSON 不被当作项目备份，恢复不覆盖原项目。
- [ ] 故意读取失败、快速导航、取消计算、带脏草稿离开；检查重试、保留与服务端真实状态。
- [ ] 三个实验室预设 → A/B → 目标原因 → 接受事件回放 → 保存记录重开，语言切换后草稿、回放和镜头保持。
- [ ] 完成五档宽度及主题/键盘/减少动效/无 WebGL 的代表性交叉检查；同环境复核性能，记录可复现步骤。
- [ ] 独立运行必要的最终受影响测试簇、`npm.cmd run build`、根目录 `git diff --check`；与任务 0 文件摘要核对，确保保护区未被本任务改变。
- [ ] 交付本地地址、变更摘要、验收结果、剩余限制及待发布清单。未经后续指令不提交、不推送、不连接生产部署。

## 终止条件与范围管理

设计文件的六项完成标准全部有证据后，本轮结束。出现数据丢失、身份混淆、有效性误导或主流程不可达的问题必须修复；范围外新模型、账户/同步和视觉新方向列入后续建议。不得不断增加功能来延长任务，也不以“仍可优化”阻止一次有边界的交付。

## 可复制的目标描述

按 `docs/superpowers/plans/2026-10-11-sitewide-improvement.md` 及关联设计完成 Y’s Formfield / Plimsoll 全站改进：贯通默认英文、可切换中文的完整工具体验；完善项目检索、章节定位及操作反馈；整理报告指标和运行对照；实现损伤实验室三种合成预设、A/B 对照及目标损伤解释；集中完善全站排版、窄屏、键盘、异常恢复和实测性能。保留既有瑞士风格、字体、音效、计算核和所有并行未提交工作，按用户最新要求由 Codex 直接实现、审查与验收。自主推进范围内的常规选择，集中测试并完成真实浏览器验收，交付本地版本和证据；不暂存、提交、推送或部署公网。
