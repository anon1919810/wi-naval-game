# 重量解释与报告打印范围交付 · 2026-10-19

**已通过父级独立验收（代码／浏览器／PDF）；本轮已提交，未推送、未部署。** 基线 `b48ed8d9d03243f184aa124b61ab45ea9d93b14b`；本轮只改 `web/frontend/src` 并新增本交付文档，既有核心、后端、部署、数据与证据文件未动，HEAD 未变。父级已持有真实的隔离基线运行（22 角色、machinery 6000 t），将在浏览器与 PDF 侧做最终独立验收，本文件不代其声称通过。

> **修订轮次**：本文件为父级第一轮独立代码评审后的**修正稿**。已按九项 source-proven 缺陷与两项附加要求逐条修正，并补足针对性回归断言；仍未通过父级验收。

## 使用效果

### 受管重量解释（工作台台账页）

台账页顶层先给出**权威平衡**：选取质量、估算质量、目标排水量与平衡差额，直接读自已保存台账；两处解释性对照（选取−估算、估算−目标）只在两侧都已知时显示，差额始终是台账保存的原值，绝不从下方分组合计重建。

下方六个呈现分组按固定顺序列出：结构 / 武备 / 固定装甲 / 机械 / 燃料 / 储备与其他。每个分组**按维度独立求和**：估重未知不会丢弃独立的已知采用合计，采用未知也不会丢弃已知估重合计（各维度单独显示，未知维度显示为未知，不给更小的部分小计）；**空组不等于零**。缺少某个固定应有角色的分组（如只有 guns 的武备组）标记为**不完整**并列出缺失角色，即使所载角色全部已知；可选 `other` 组不虚构缺失角色。条形图与下方角色列表读同一份纯投影，所以图形与列表不可能互相矛盾；条带从零线起算，已保存的负值向左延伸，已保存的零是真正的零，未声明的取值显示为未知且不绘制条带。

**与权威平衡的核对**：在本读数之外单独给出「可确定的角色合计」与「台账平衡」两行，并给出裁决——**一致**／**不一致（台账平衡为权威并保持不变）**／**无法核对（至少一个角色未知或冲突）**。台账平衡始终读自台账，绝不从合计重建，也绝不改写；核对只作陈述，不覆盖权威值。

每个角色保留来源估重、采用质量、策略（估算／声明／无）与项目 ids，并给出「采用−估重」差值。未知（—）、零、负值三种状态彼此独立。**来源身份被保存多次者折叠为一行显式冲突**：即使重复行取值完全一致也不做 first-wins、不做求和；该行的估重、采用、策略、绑定与差值均未知，所属组合计保持未知，冲突行没有编辑入口，原始完整台账表仍可在下方审计。可选 `other` 载荷不带来源估重也无需绑定，不是缺失角色。

### 分组选择与真实绑定揭示

分组按钮只打开该组的阅读面板，**选择本身不写入设计**；「揭示原绑定」按钮是显式请求，打开既有绑定折叠区并把焦点落到该角色真实的绑定／人工质量控件上，不更改任何值。

### 待确认／失败

`pending` 或 `failed` 时，新读数、图表、新操作与**原台账表**一并隐藏，避免旧预览的残留数值冲淡未知状态；状态与 `ShipDesignChapter` 一致采用 error-first 的完整 host 状态：队列错误或 setup 错误即 `failed`，`disabled`／busy／队列 pending／host pending 即 `pending`。原绑定、人工质量、来源／位置入口保留（pending 期间禁用），原队列可按既有方式重试；错误态下不展示任何新揭示动作。显式「揭示」只聚焦该角色真实且可用的控件。

### 冻结报告

冻结 `ship_design` 结果在既有 envelope 闸门（requested、completed／partial、kernel 身份一致）之后挂载同一只读读数。**冻结自身读数即完整读数**：即使没有任何对照，也保留每个角色的估重、采用、采用差值、策略、项目 ids 与显式冲突说明；只隐藏选择与编辑控件。带本次运行与 basis 身份。配置对照中的**冻结逐类角色对照**给出两次保存结果的**有序并集**：每个角色两侧各自的估重、采用、策略与绑定，差值表述为「对照−当前」。**两个质量维度各自独立**：一侧估重未知不会隐藏另一侧已知的采用差值（反之亦然），单元格对未知维度显式写出「未知」而非静默省略。策略或绑定变化是类别变化，不是质量差；一侧缺失的角色在该侧为未知而非零；任一侧冲突则不给差值；两侧不合基准或任一侧基准为空白字符串时不陈述任何角色差值，纯模型的非可比对绝不暴露任何数值差值。可比时不再重复堆一份「有变化的角色」列表。

### 报告打印范围

报告页新增本页局部**打印范围**控件（仅影响纸面，屏幕、已存快照与下载保持完整，不更改任何项目）：

- **可读原生报告默认「设计报告」**：纸面保留可读原生设计、其诊断、被请求的物理阶段、运行／修订／基准身份、始终可见的请求指纹，以及已选对照；重复的原格式文本、原生键值审计与来源附录不上纸。默认范围判定改用与读数一致的既有 envelope 闸门（`propulsionEnvelopeGate`：requested、completed／partial、kernel 身份）叠加可读 schema／method／status，而非更弱、仅校验 schema 的重复判定；kernel 不符或未请求的原生阶段一律回落完整范围，其回退来源内容不被误判为重复。
- **物理／无可读原生结果默认「完整报告」**：保持既有打印行为，含来源与方法附录与原始报告文本。**兼容阶段（如 sps_compat）**没有可读原生替代，其原格式文本、原生键值审计与来源材料在纸面上保留、不标记为次要材料；只有确实存在完整可读原生替代时才抑制这些重复材料。

两个打印按钮、浏览器打印命令与 Ctrl+P 共用唯一的 `beforeprint`／`afterprint` 生命周期。打印前的展开遍历是**祖先感知**的：嵌套在隐藏次要区域或原始载荷内的 details 与其祖先一同被视为隐藏，设计范围既不去展开、也不去挂载被排除的附录（不触发来源遍历），切换范围时也不会因上一次完整打印而把隐藏材料重新打开；在重复打印、切换范围与卸载时恢复读者原有的 details 状态；单位与快照不受影响。

报告专属打印样式（`reportPrint.css`）：A4 纵向、白纸深字、明确页边距；干舷剖面按自身比例填满栏宽；**两张长图（武备 960×2092、装甲 960×1536）在纸面上被限定到可打印高度并各起新页，不再被拉满栏宽而溢出或被裁切**，其可读呈现是**由同一份纯数据（banks／bands）生成的报告专属结构化读数**（屏幕隐藏、纸面显示；屏幕与下载的完整交互 SVG 不变）；完整范围显式覆盖 `Sps3b3.css` 对 `.sps-saved details` 的整体隐藏，使已保存的原生审计在完整纸上重新显示；编辑／下载／导航类控件（`.freeboard-actions`、`.armament-actions`、`.armour-diagram-actions`、`.report-actions`、`.report-units`、对照与 `.no-print`）在纸上隐藏；长表表头跨页重复，行与标题避免跨页断裂；条形图颜色精确保留。

## 集中独立验收

| 范围 | 实际证据 |
|---|---|
| 相关前端簇 | 本机执行 12 文件、**199 用例全部通过**（`weight-breakdown`、`report-print`、`report`、`report-navigation`、`report-comparison`、`native-report-readings`、`native-report-metrics`、`design-feedback`（纯）、`design-feedback-ui`、`ship-design`、`hull-freeboard`、`workspace-lazy`）。未重跑不变的核心／后端全量。 |
| 新增用例 | 边界／交互用例：`weight-breakdown.test.tsx` **50 个**（含本轮新增 16 个），`report-print.test.tsx` **13 个**（含本轮新增 2 个）。 |
| 构建 | `npm run build`（`tsc -b && vite build`）通过，退出码 0；仅保留既有 Scene 约 582 kB 的构建体积提示。 |
| 关键边界 | 未知／零／负值相异；两维度独立求和与独立差值；重复角色身份折叠为单行冲突且不求和；缺固定角色的分组不完整并列出缺失；确定角色合计与台账平衡核对（一致／不一致／无法核对）且平衡不被覆盖；平衡读自台账且与分组不符时仍显示原值；baseline 仅在 schema／method／status／已知非空 basis 全部相符时才标变更；已知转未知计为变化、两未知不算变化；对照方向为对照−当前、缺失侧为未知、未知维度显式写出。 |
| 冻结完整性 | 冻结自身读数无需对照即保留每个角色的全部事实与冲突说明；只读、无选择、无编辑。 |
| 冻结闸门 | 未请求／失败／kernel 不符 envelope 下冻结读数与旧平衡都不出现；`other` 不在可比时重复堆叠。 |
| 打印生命周期 | 设计范围打印不挂载来源附录、不打开原生键值审计（含嵌套 details）；完整范围打印重新展开并挂载附录、显示已保存原生审计；重复打印与范围切换后读者 details 状态复原；卸载移除监听。 |
| 兼容阶段保留 | 无完整可读原生替代时，兼容阶段的主报告文本与原生审计不标记为纸面次要材料。 |

重跑方式（`web/frontend`）：

```
npm test -- src/__tests__/weight-breakdown.test.tsx src/__tests__/report-print.test.tsx src/__tests__/report.test.tsx src/__tests__/report-navigation.test.tsx src/__tests__/report-comparison.test.ts src/__tests__/native-report-readings.test.tsx src/__tests__/native-report-metrics.test.ts src/__tests__/design-feedback.test.ts src/__tests__/design-feedback-ui.test.tsx src/__tests__/ship-design.test.tsx src/__tests__/hull-freeboard.test.tsx src/__tests__/workspace-lazy.test.tsx
npm run build
```

## 变更文件

新增：

- `web/frontend/src/components/weightBreakdownModel.ts` — 纯投影 `readWeightBreakdown(result, baseline?)` 与 `weightComparisonRows(current, comparison)`，六分组、维度独立求和、缺失角色覆盖、冲突折叠、变更闸门、平衡核对、对照并集。
- `web/frontend/src/components/WeightBreakdownReadings.tsx` — 顶层只读重量读数（平衡、核对、分组、条形图、角色列表、分组选择、揭示按钮；冻结时保留全部角色事实）。
- `web/frontend/src/components/WeightRoleComparison.tsx` — 冻结逐类角色对照表（对照−当前，逐维度显式未知）。
- `web/frontend/src/i18n/weightBreakdown.ts` — 中英双语完整词典（含打印范围、报告身份、核对与覆盖文案）。
- `web/frontend/src/styles/weightBreakdown.css` — 读数与对照样式（主题 token，390px 无页面横向溢出）。
- `web/frontend/src/styles/reportPrint.css` — 报告专属打印范围与 A4 纸面规则（长图限高、报告专属结构化读数、完整范围原生审计覆盖、纸面控件隐藏）。
- `web/frontend/src/__tests__/weight-breakdown.test.tsx` — 50 个纯投影、读数 UI 与台账 host 状态用例。

修改：

- `web/frontend/src/pages/Report.tsx` — 打印范围状态、`defaultPrintScope`（改用既有 envelope 闸门）、范围控件、纸面身份条、范围感知的附录挂载。
- `web/frontend/src/components/useReportPrint.ts` — 新增范围参数与**祖先感知**的 `print-secondary`／原始载荷排除；只展开当前范围内的 details；生命周期语义不变。
- `web/frontend/src/components/SourceInspector.tsx` — 折叠的指纹／来源／方法／来源附录标记为纸面次要材料。
- `web/frontend/src/components/Sps3b3Readings.tsx` — 冻结闸门后挂载只读重量读数；仅当存在完整可读原生替代时才把原生键值审计与原格式文本标记为纸面次要；兼容路径保留主报告。
- `web/frontend/src/components/ShipDesignEditor.tsx` — 台账章节改用 error-first 完整 host 状态、改用重量读数、真实绑定揭示聚焦可用控件、pending／failed 隐藏原表与新动作。
- `web/frontend/src/components/ArmamentComposition.tsx` — 冻结时新增报告专属结构化读数（纸面显示，屏幕无用例可见副本）。
- `web/frontend/src/components/ArmourDiagram.tsx` — 同上。
- `web/frontend/src/pages/Workbench.tsx` — 向台账章节传入已保存结果作为 baseline。
- `web/frontend/src/components/DesignFeedback.tsx` — 冻结摘要可比时挂载角色对照并抑制重复的有变化角色列表。
- `web/frontend/src/__tests__/report-print.test.tsx` — 打印范围用例 13 个（含本轮 kernel 不符回落与兼容阶段保留）。

## 范围与限制

- 只读、纯投影：`readWeightBreakdown` 与 `weightComparisonRows` 不计算任何船舶数值，不重算权威平衡；核对只是陈述，绝不覆盖台账值；报告与工作台均不写入项目、快照或导出。
- 严格可读性：仅接受受支持的 schema `plimsoll-ship-design-result-1`、method `ship-design-native-v1`，以及 `available`／`partial` 状态；其余一律命名原因并隐藏残留数值。基准比较仅在两侧基准为**已知非空字符串**且相等时成立（空白基准不算基准）。台账 `complete` 为**严格布尔**：缺失或非布尔即未知，不臆造 false。
- 强制分组映射与角色折叠：未知的未来角色归入「储备与其他」；重复来源身份折叠为单行冲突；固定分组的应有角色缺失即标记不完整。
- 打印样式作用域：除 `@page` 的 A4 页面盒（CSS 无法按选择器限定）外，所有新增打印规则都限定在 `.report-page` 之下，不改变普通工作台。长图的纸面结构化读数只在 `frozen`（报告）态生成，屏幕隐藏，屏幕与下载的完整交互 SVG 不变。
- 未提供 PDF 服务端接口；本轮不声称 PDF 生成已验收。

## 待父级独立验收 / 未决

- **代码独立验收**：父级独立复核纯投影与 UI 行为、两维度独立求和与差值、缺失角色覆盖与平衡核对、冲突／未知／空白基准／严格 complete 边界、error-first host 状态，以及打印生命周期与兼容阶段保留。
- **浏览器验收**：真实浏览器中的分组选择、揭示聚焦（真实可用控件）、pending／failed 隐藏、屏幕完整性、兼容阶段主报告留存。
- **PDF／纸面验收**：实际 A4 打印／导出中，两张长图（武备 960×2092、装甲 960×1536）的**报告专属结构化读数**是否清晰可分页，长表是否完整可读、无裁切，完整范围的原生审计是否按预期重新显示；本机只在 jsdom 与构建层验证。父级将渲染真实 A4 PDF 以确认；若结构化读数仍需调整，这是既有 spec 允许的同一纯数据的纸面呈现，屏幕与下载不受影响。
- **偏差说明**：`weight-breakdown.test.tsx` 50 例、`report-print.test.tsx` 13 例，高于计划建议的约 20–26 例；原因仍是把每个边界（未知／零／负、维度独立、缺失角色、平衡核对、单行冲突、空白基准、严格 complete、对照方向、host 状态、打印恢复）各自独立成例，未构造组合矩阵。
- **未执行检查（父级所有）**：真实浏览器交互、真实 A4／PDF 分页与图形可读性。


---

## 父级验收（2026-10-19 19:30，DSH 接手 Codex 父级角色）

**结论：验收通过，附 1 项不阻塞残留。** 基线 `b48ed8d` 未变，工作树 20 项改动仍未提交（等用户授权）。记录文件：`reverse-engineer-anything/outputs/weight-report-2026-10-19/parent-acceptance.json`。

### 先纠正一处事实：那份 rejected 评审已经过期

`code-review.json` 写于 14:08，而 worker 在 14:17–14:33 又改了一整轮，之后无人重审。本轮按**当前工作树**逐条复核，不做重跑。

| # | 级别 | 位置 | 判定 | 证据 |
|---|---|---|---|---|
| 1 | P1 | ShipDesignEditor.tsx:668-671,696 | 已修 | `queue.error \|\| host.error` → failed；`disabled/busy/queue.pending/host.pending` → pending；旧台账表被 `state==='ready'` 闸住。用例：*is failed on a queue error…* / *is pending on a busy…* |
| 2 | P2 | weightBreakdownModel.ts:220-240 | 已修 | 估重与采用各自累计、各自可为未知；采用差值才要求两者已知。用例：*keeps the two group dimensions independent* |
| 3 | P2 | weightBreakdownModel.ts:415-421 | 已修 | 分组由**已标记**的角色重建。用例：*rebuilds the groups from the marked roles…* |
| 4 | P2 | WeightBreakdownReadings.tsx:99-117,231-238 | 已修 | 冻结态保留全部角色事实与冲突说明，只隐藏选择/编辑。用例：*keeps every role fact in the frozen own-reading* |
| 5 | P2 | weightBreakdownModel.ts:243-268 | 已修 | 缺失固定角色列出（`other` 豁免）、complete 与核对裁决同屏。用例：*states the reconciliation verdict…* |
| 6 | P2 | Sps3b3Readings.tsx:59-64,118-126 | 已修 | `nativeDuplicate=native && propulsionEnvelopeGate`，兼容阶段主报告保留 |
| 7 | P2 | reportPrint.css:138-143 | 已修 | 纸面重新显示 `.sps-saved details`，设计范围 `!important` 仍优先 |
| 8 | P2 | weightBreakdownModel.ts:154-156,410-412 | 已修 | 空白基准归一为 null，双向都不可比。用例：*treats a blank basis as no basis* |
| 9 | P2 | reportPrint.css:145-149 | 已修 | 下载/编辑/导航控件纸面隐藏 |

### 验收期修正的三处（都是我在真跑之后才暴露的）

1. **两张长图在纸面上是 3–4 pt 的糊**（实测 p10 3.16 pt、p17 3.86 pt、p19 4.27 pt）。原 CSS 把 960×2092 的图压到 235 mm 高，"不溢出"满足了，但字看不清。改为**纸面不印这两张序列化长图**，由同一份 banks/bands 生成的结构化读数承载（实测 9.84–12 pt）。
2. **390 px 下整页横向溢出 116 px**（`scrollWidth` 506 > 390）：报告身份条里的 method/request JSON 是不换行长 token，而样式只给 `code` 加了断行。改为身份条所有子项 `min-width:0; overflow-wrap:anywhere`，实测 375 px。
3. **强制分页留下近空白页**（第 9 页仅 49 字符，只有一句小节导语）。去掉 `.print-only-structured` 的 `break-before`，页数 21 → 19，无低于 120 字符的页。

修正后回归：`report-print` + `weight-breakdown` **63 用例通过**，`npm run build` 退出码 0。

### 真跑出来的纸面证据（隔离验收服务 + 自有 profile 的 Edge + CDP）

| 产物 | 页数 | 字符 | 出界字符 | 最小字号 |
|---|---|---|---|---|
| final2-en-design.pdf | 19 | 25,018 | 0 | 4.27 pt |
| final2-zh-design.pdf | 17 | 12,868 | 0 | 4.27 pt |
| final2-en-full.pdf | 17 | 37,653 | 0 | 4.17 pt |

- **打印生命周期**：三份都触发 `beforeprint`/`afterprint`；原有 16 个 disclosure 的开合状态**零变化**；完整范围额外挂载 26 个审计分组且全部保持折叠；原始阶段载荷从未打开；单位/快照/范围选择复原。
- **范围生效**：设计 26,228 字符 vs 完整 38,902 字符，完整版独有的 `Provenance` 附录材料确实上了纸。
- **屏幕**：390 px 无横向溢出；深色 `data-theme=dark`（纸面样式不受影响）；中文 `zh-CN` 渲染正常（受管重量台账／权威平衡）。
- **数值对账**：六组估重/采用与权威平衡四项，全部与 `baseline-expectations.json` 一致（容差 0.02 t），核对裁决为"确定角色合计与台账平衡一致"。

### 残留（不阻塞）

- **P3 · 干舷剖面面板纸面 4.17–5.22 pt**。这不是本轮引入的（来自干舷交付轮），且八个端点的数值另有 8.64–12 pt 的可读列表；不可读的是该图自带的说明文字与表格。建议下一轮给它做同样的 print-only 结构化替代。

### 尚未真跑的

- **工作台编辑链路**：machinery 6000 → 6100 t、角色揭示、pending/failed 恢复，目前只有两条针对性用例 + 代码核对，**没有对着活服务跑过**。这是下一轮第一件事。
