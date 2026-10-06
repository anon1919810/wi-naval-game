# Plimsoll 第二组：运行与报告阅读实施计划 · 2026-10-06

> 执行分工：遵循用户 AGENTS.md，Codex 规划、读代码、审查与独立验收，OpenCode 实现。用户已于 2026-10-06 授权“规划完成自动执行”；按下列功能单元顺序实施并验收。

**目标：** 打开运行时立即辨认真实状态；打开报告时先读身份、有效性和关键数字，再按阶段定位完整结果、诊断与来源。

**架构：** 保留现有 API、hash 路由、Run 的轮询及 Report 的不可变保存结果读取。增加小型纯函数模块管理已请求阶段、关键读数和阶段链接；运行页与报告共用阶段索引，继续使用 StageStatus、StabilityPlot、FloodingResults。报告来源移入正文审计区，避免 1024 桌面形成三栏。

**技术：** 现有 React / TypeScript / Vite / Vitest，不增加依赖。

**依据：** [第二组设计提案](next-workspace-design-2026-10-05.md)、[第一组实际交付](workbench-group-one-2026-10-06.md)，以及 2026-10-06 当前 checkout；HEAD 仍为 `c68a289`，不能只依据已提交代码。

## 范围与不变条件

- 桌面 1440×960 / 1024×900，浅深色；标题 Space Grotesk，正文 Inter。沿用第一组的紧凑操作区、编号和细线。
- 本轮只做第二组。第三组转场、移动端、新船图、计算评分、后端/内核/API、部署和依赖升级均不进入本轮。
- 保留第一组未提交成果，以及并行字体、许可/文档、index.html、portfolio.css、tokens.css 的实际内容；开始与结束逐文件 SHA256 比对，不暂存整个工作区。
- 不要求先提交才能开始。未经另行要求，不提交、不推送；文档状态明确区分计划、实现、验证与部署。
- 只使用保存结果，不请求最新项目替换 input_snapshot。单位选择只作用于报告本页，不能更改快照、请求指纹或 JSON/CSV 导出。
- 运行 `queued/running/completed/partial/canceled/failed` 与 `cancel_requested` 分开。API 没有逐阶段实时进度：不画完成百分比，不宣称某阶段正在计算。
- 目录仅含 `requested === true` 的阶段，沿用 STAGE_ORDER；未知阶段放在已知阶段之后并保留名称，不因排序丢失。
- Unknown、Unavailable、未请求、模型越界与真实零分开。严重诊断直接显示，计算完成不解释为史实、设计或适航认证。
- 保留对比条件、单位、方法版本兼容检查和最多八个既有可比指标；不扩大指标范围，不重新计算结果。
- 按功能簇集中测试；每个单元只做必要目标检查，第二组收束时跑集中簇，不在每个编辑后跑回归。

## 当前代码事实

1. `Run.tsx` 每 1500ms 读取运行，终态停止；结果阶段有 `.slice(0, 4)`，破损另外渲染。全请求指纹常驻摘要，没有独立运行页测试文件。
2. `Report.tsx` 保留 ShipProfile，占据封面空间；阶段卡片连续排列，但没有阶段目录。GZ 曲线另列于全部卡片之后，应回到对应阶段下。
3. `StageStatus.tsx` 的诊断全部在 details 中，严重错误也被默认隐藏；普通摘要最多八项，不能当作完整报告。
4. `StageStatus` 的完整阶段 JSON 只有 rawOpen 后才挂载；仅改打印 CSS 不会生成缺失的 DOM。`SourceInspector` 在右侧 255px 栏，长指纹始终可见。
5. `fixtures.ts` 把载荷放在顶层、平衡写成 draught_m；实际协调器输出不同，必须先补真实形状，不能让旧夹具反过来定义投影。
6. App 和 Portfolio 用 hash 识别页面；裸 `#stage-loading` 会失去工具路由。现有路由读取 `runs/reports` 后的第二段作为 id，可保留该 id 并增加阶段尾段。
7. 对比读取没有独立错误区，失败会替换整份报告；快速切换对照也缺少最新选择守卫。此处只修阅读流程所需的错误隔离和旧响应拒绝。

## 阅读设计

**运行页：** 顶部英文 Run、运行 id 和舰船上下文；紧凑状态区显示真实运行状态、工况、保存修订、返回与取消/报告入口。完整指纹和时间放入元信息。排队/运行使用无百分比等待反馈；取消请求显示“已请求取消”，直到服务端实际返回 canceled 才显示“已取消”。有结果后出现全部已请求阶段索引与摘要，部分或取消结果仍可打开报告，破损证据不重复渲染。

**报告页：** 身份与状态 → 关键读数 → 按阶段连续正文 → 审计信息。舰名为主标题，Report 为小号定位；工况、保存修订、运行 id、整体有效性和史实验证状态在首屏可读。删除通用 ShipProfile，不补画任意船体。显示单位、导出、打印、对比放在安静的操作区。

**阶段定位：** 1440 与 1024 均用约 200px 左索引和自适应正文；来源不另开第三栏。索引只承担定位，不把正文变成标签页或默认折叠。点击后滚动到章节并把键盘焦点放到该章节标题；初始深链接只定位，不抢已存在焦点。长表格局部横向滚动。

阶段地址采用 `#/runs/{runId}/stages/{name}` 与 `#/reports/{runId}/stages/{name}`，保留旧 `#/runs/{id}` / `#/reports/{id}`。未知或未请求阶段的尾段忽略，仍显示当前页。阶段链接可复制；无 runId 的独立 Report 预览只提供按钮定位，不生成虚假运行地址。

正文定位目标统一为 `id="stage-{name}"`，章节标题 `tabIndex={-1}`；设置顶部滚动留距，避免粘性页眉遮住标题。GZ 曲线与破损证据包含在相同阶段目标内。

## 关键读数的明确投影

| 首屏读数 | 保存路径：result.stages 下 | 标签与单位 |
|---|---|---|
| 当前总质量 | loading.data.values.total_mass_t | 所选工况总质量，t，可按显示偏好转换 |
| 当前水线 | equilibrium.data.waterline_above_keel_m | 龙骨基准水线高度，m；不得改称由前端推算的吃水 |
| 横倾 | equilibrium.data.heel_deg | 横倾角，deg |
| 初稳性 | hydrostatics.data.values.gm_t_m | 初稳性高 GM，m；保留对应阶段的定义与边界 |
| 功率工作点 | resistance.data.power_rows | 仅唯一工作点时显示 shaft_power_kw，并同时标 speed_kn；多工作点显示“多个工作点，见阻力与功率”，不挑第一行 |
| 续航 | endurance.data.values.range_nm | 稳态续航，nmi；同时保留工作航速、来源、估算标记与适用假设 |

首屏数值要求阶段已请求且 status 为 completed、对应字段为有限数字；模型越界/资料不足/失败/取消阶段不呈现普通结果数字。整体 partial/canceled 不妨碍显示其中已完成阶段的保存事实。功率工作点还必须有有限航速、完整输出和主结果/模型适用性；不完整或非主试算保留原因并引导到详情。缺项原因来自保存 stage.reason / 状态或明确“本次结果未给出此字段”，不补输入、不借其他工况、不做平均或插值。

动力阶段的 `values.power_design_kw` / `power_trial_kw` 是保存的动力声明口径；如在阶段详情突出它们，必须标设计/试航声明，不能冒充该阻力工作点的轴功率。续航不得用 propulsion 的历史 `values.range_nm` 代替 endurance 的本次稳态结果。

## 模块与接口

新增 `web/frontend/src/components/resultReading.ts`：

- `requestedStages(result: AnalysisResult): Array<{name: string; stage: StageEnvelope}>`：只做过滤和稳定排序。
- `reportReadings(result: AnalysisResult): ReportReading[]`：只投影上述六种读数。
- `ReportReading = { key: string; stage: string; label: string; value: number | null; dimension?: Dimension; storedUnit?: string; canonicalUnit?: string; state: 'known' | 'unknown' | 'not_requested' | 'unavailable' | 'model_limit' | 'failed' | 'canceled' | 'multiple'; reason: string | null; context: string | null; source: string | null; estimate: boolean | null }`。来源使用第一组 declaredSource 保留结构化声明；range 不伪装长度转换。
- `stageHref(page: 'runs' | 'reports', runId: string, stageName: string): string` 与 `readStageTarget(hash: string, page: 'runs' | 'reports', runId: string): string | null`：encode/decode 段并核对页和 id。

新增 `StageIndex.tsx`：`{page: 'runs' | 'reports'; runId?: string; stages: Array<{name: string; stage: StageEnvelope}>}`。渲染可访问定位链接；不加载数据、不管理运行状态。

新增 `ReportReadings.tsx`：只消费 reportReadings 与 UnitProvider。新增 `useReportPrint.ts`：只管理本页打印准备/恢复，不承担导出或数据加载。

修改 Run.tsx / Report.tsx / StageStatus.tsx / SourceInspector.tsx / workspace.css；如需从 Run 直达报告阶段，仅在 App.tsx 给现有 onReport 回调增加可选阶段参数，不改项目/身份逻辑。

## 实施与委派单元

### A：保存字段与共同阅读基础

文件：新增 resultReading.ts、StageIndex.tsx；修改 fixtures.ts；新增 result-reading.test.ts。

- [x] 先写投影测试：真实 loading.values、waterline_above_keel_m、GM、单/多功率工作点、稳态续航；0 与 null、未请求、越界残留数字、partial 中完成阶段、结构化来源明确区分。
- [x] 在新测试内定义真实形状夹具，保留共享旧夹具及既有有限指标对比覆盖；不整体替换 fixtures.ts。
- [x] 实现接口、未知阶段稳定排序和保留 hash 页/id 的阶段链接。
- [x] Codex 对照实际协调器独立审查；首轮发现类型/单位问题，复审发现定位竞态和缺失功率声明后接回修正。投影与定位两文件最终 27/27，通过只读复审。

### B：运行状态与全部阶段

文件：Run.tsx、StageStatus.tsx、必要的 App.tsx 回调；新增 run.test.tsx。

- [x] 写运行测试：六种状态、queued/running 轮询与终态停止、已请求取消未当成 canceled、取消失败、离开页后旧响应、无结果、有取消前保存结果。
- [x] 压缩身份/状态头，折叠元信息，移除四阶段截断，所有已请求阶段都有定位；无结果时不显示虚假的阶段执行状态。
- [x] 严重诊断（含 blocking）从 details 移到直显区域；普通诊断/假设可展开。阶段原因去重后仍保留诊断代码、路径与来源路径；根诊断去重在 C 收束。
- [x] 把 FloodingResults 放在唯一的 flooding 阶段中，保留停止原因、守恒与剩余稳性直接入口，避免 Run 再复制一份。
- [x] Codex 独立目标检查最终两文件 27/27（含读取恢复与专项结果边界补修）；单独 TypeScript/Vite 构建通过。并发构建曾出现一次本机内存分配失败，停止并发后独立复跑成功，未改依赖或机器配置。

### C：报告封面、目录与阅读

文件：Report.tsx、ReportReadings.tsx、SourceInspector.tsx、workspace.css；修改 report.test.tsx / display-units.test.tsx，新增 report-navigation.test.tsx。

- [x] 写报告测试：保存身份/修订、六种摘要投影、ShipProfile 消失、目录等于 requested 集合、GZ 与破损在各自章节且不重复、定位不离开 hash 工具页、复制/重开深链接、键盘焦点。
- [x] 实现紧凑封面、200px 索引和连续正文；SourceInspector 移到正文审计区。保留所有完整阶段数据入口、方法边界及原有专项结果表/曲线，不删除首屏之外的数据。
- [x] 正文中的严重诊断始终直显；长来源/指纹可折叠但完整可读，缺项原因跟随读数。
- [x] 报告主要加载错误与对比错误分开；对比失败不能藏起主报告。新运行/新对照到来时清旧状态、拒绝晚到响应；取消对照能清除旧错误。
- [x] 保留本页单位、规范单位导出和既有对比范围；目标检查：`npm.cmd run test -- src/__tests__/report.test.tsx src/__tests__/report-navigation.test.tsx src/__tests__/display-units.test.tsx`。

### D：打印与集中验收

文件：useReportPrint.ts、StageStatus.tsx、SourceInspector.tsx、workspace.css；新增 report-print.test.tsx；更新实际交接与 CHANGELOG。

- [x] 用 beforeprint/afterprint 准备并恢复打印所需折叠内容；包括完整诊断、假设、方法、来源与指纹。对于来源只存在于保存快照/阶段数据的情况，打印审计附录按真实 source 元信息及路径列出声明，不能依赖此前点击展开。
- [x] 原始阶段 JSON 保持屏幕完整数据入口；打印不展开船体采样、求解迭代等海量原始数组。实际受控结果包约 3.6MB，来源审计和重要结果必须可打印，但原始数据导出与阅读报告保持各自用途。
- [x] 先用 CSS 控制白底、控件/索引隐藏、正文单栏、解除 max-height/overflow 限制；只有准备 React 延迟内容时才在 beforeprint 使用 flushSync。禁止放进 render/effect 或常规交互循环。
- [x] 长阶段允许分页，表头可以重复；不把整个长 stage-card 强制塞在一页。打印完或取消打印，屏幕折叠状态与单位选择恢复。
- [x] 测试默认折叠时的打印准备、打印恢复、事件监听 cleanup、严重错误/结构化来源保留；目标命令：`npm.cmd run test -- src/__tests__/report-print.test.tsx`。
- [x] 最后统一运行下方功能簇、构建、真实桌面浏览器及保存报告 PDF 检查。Codex 逐项独立验证，读取 OpenCode changed_files，保护文件 SHA256 比对；失败只补跑受影响检查。

## 集中验收命令

在 web/frontend：

```powershell
npm.cmd run test -- src/__tests__/run.test.tsx src/__tests__/results.test.tsx src/__tests__/result-reading.test.ts src/__tests__/report.test.tsx src/__tests__/report-navigation.test.tsx src/__tests__/report-print.test.tsx src/__tests__/display-units.test.tsx src/__tests__/anonymous-workspace.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/workbench-hierarchy.test.tsx src/__tests__/advanced-inputs.test.tsx
npm.cmd run build
```

在仓库：`git diff --check`。最终执行证据记录在本轮交接文档；实现期间不把计划命令当成通过证据。

实际验收分配：1440×960 与 1024×900 浅/深色，用同一真实完成运行检查八个阶段、长指纹/结构化来源、hash 定位与返回、键盘与本页单位。部分/取消/无结果/失败、多工作点、专项长表内容与异步错误由组件测试覆盖；打印生命周期由事件测试和 Chromium Page.printToPDF 实际路径覆盖。Windows 原生打印对话框及手动按钮/Ctrl+P 对话框操作未验收，不声称已完成这些 UI 操作。

优先使用已有保存运行，不为 UI 验收重复计算。若隔离预览没有结果，只新增一次受控基线运行，记录其项目/修订/工况/请求；mock fixture 只验证 UI 状态，不能作为真实保存计算或 PDF 证据。PDF 检查第一页身份/单位、越界/缺项原因、严重诊断、全部阶段、来源与指纹、长表格分页；浅深色各打印一次同一结果即可，不重复计算。

## 五项重点审查

1. 真实后端字段与旧前端夹具不同：A 的投影测试和 C 的封面测试必须固定真实形状。
2. hash 路由被页内锚点破坏或定位导致重挂载：A 链接测试、C 集成定位测试必须证明 id 与显示单位选择保持。
3. 取消请求/部分结果被误称完成或被藏起：B 覆盖轮询、取消及结果并存状态。
4. 对比晚到响应替换最新选择、失败藏主报告：C 用 deferred promise 按相反完成顺序验证。
5. 折叠区未挂载导致打印漏诊断/来源：D 用默认关闭状态触发 beforeprint，并检查恢复；真实 PDF 另行验证。

## OpenCode 执行约定

同一任务复用一个会话，A → B → C → D 顺序 continue；每次只下达一个有明确文件边界和可运行命令的单元。brief 必须列出保护文件、不得提交/部署、真实字段路径、完成条件和允许的命令，不让 OpenCode自行扩大范围或反复全量测试。

Codex 在每个单元结束读 changed_files 与实际 diff，不以 OpenCode 的测试汇报代替独立验收；两轮审查未通过时按用户规则接回。运行失控则 cancel。用户已授权自动执行；本任务加载 opencode-delegate，复用同一 OpenCode 会话顺序实施并由 Codex 独立验收。

## 官方 API 核对

打印准备参考 [MDN beforeprint](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeprint_event)、[MDN Printing](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing) 与 [React flushSync](https://react.dev/reference/react-dom/flushSync)：优先打印 CSS，仅在浏览器要求打印前同步准备 React DOM 时使用 flushSync。屏幕布局或一般状态变化不使用它。

第二组验收后再规划第三组转场；冻结时做一次全量前端回归与最终打印检查，再按独立发布请求处理部署。

## 最终验收记录 · 2026-10-06

C 独立三文件 51/51；D 打印生命周期七项纳入最终集中簇。最终集中簇为 11 文件、182/182；打印发现 shp 单位标注后，受影响三文件 38/38，最终构建与 git diff --check 通过。11 个保护文件 SHA256 一致。真实浅深色 PDF 均 35 页，929 个来源路径、三个完整指纹、八阶段和全部诊断字段完整，打印状态恢复；原始 JSON 未因打印挂载。完整交付、实际范围与验证限制见 [第二组交接](run-report-2026-10-06.md)。
