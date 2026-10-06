# 运行与报告阅读 · 2026-10-06

第二组已本地实现并验收，未提交、推送或部署。基于 HEAD `c68a289` 与当前未提交工作；保留第一组编辑页成果、Space Grotesk / Inter 字体及并行全局样式。第三组转场仍待独立规划。

## 实际交付

- 运行页集中显示舰船、运行 id、保存修订、工况和真实状态；指纹与时间折叠。六种运行状态分别呈现，“已请求取消”持续读取到服务端实际终态；取消失败、初次读取失败与已加载后读取失败都有恢复入口。
- 不再截取前四个阶段。所有已请求阶段按既有顺序定位，未知阶段保留名称并置后。部分或取消的保存结果仍可阅读。破损证据与 GZ 图各自归入对应章节，只出现一次。
- 报告先显示保存身份、有效性和六项关键读数；删除通用船图。总质量、水线高度、横倾、GM、阻力功率工作点和稳态续航均读取各自保存字段；真实零、未知、未请求、失败和模型越界分开。多个功率工作点不挑第一行，也不借历史动力声明替代本次工作点或续航。
- 约 200px 左阶段索引与连续正文并排，审计信息置于正文底部。点击或键盘回车定位并聚焦章节标题；初始深链接仅滚动，不抢焦点。地址保留 `#/runs/{id}/stages/{name}` 或 `#/reports/{id}/stages/{name}`，旧基础地址继续有效。
- 严重诊断和 blocking 警告直接显示，普通诊断与假设可展开。整体与阶段诊断按实际证据匹配去重，保留带阶段标记的整体独有诊断和更强的严重发现；代码、消息、路径与来源路径均保留。
- 对比失败只影响对比区；切换、清除、换运行和离开页面后拒绝旧成功/失败响应。只比较双方已请求且完成的有限、已分类顶层数值，最多八项，继续核对工况、单位与方法版本。报告本页单位选择不修改保存快照、指纹或导出。
- 打印前展开诊断、假设、方法、指纹和完整来源附录，结束后恢复原有折叠状态与单位。来源附录平时可按需展开，合并相同声明及估算状态，并列出所有实际路径；true、false、未知估算状态不混合。
- 浅深色均打印白底单栏；控件和阶段索引隐藏，长章节与来源可以分页，诊断子容器和审计文本解除高度/滚动限制。完整原始 JSON 保留屏幕与导出入口，打印不展开几何采样、迭代等海量数组。
- 实际 PDF 检查补上了设计/试航功率声明的 `shp` 单位标记，保存数字和声明口径不变。首屏的字段/null 技术文案改为明确的未知说明。

## 独立验证

集中前端功能簇 **11 文件、182/182** 通过：run、results、result-reading、report、report-navigation、report-print、display-units、anonymous-workspace、portfolio-transitions、workbench-hierarchy、advanced-inputs。覆盖六种运行状态、取消边界、读取恢复、阻塞残留值、单/多工作点、结构化来源、路由/焦点/单位保持、反序异步对比及打印准备/恢复。

```powershell
# web/frontend
npm.cmd run test -- src/__tests__/run.test.tsx src/__tests__/results.test.tsx src/__tests__/result-reading.test.ts src/__tests__/report.test.tsx src/__tests__/report-navigation.test.tsx src/__tests__/report-print.test.tsx src/__tests__/display-units.test.tsx src/__tests__/anonymous-workspace.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/workbench-hierarchy.test.tsx src/__tests__/advanced-inputs.test.tsx
npm.cmd run build
# 仓库根目录
git diff --check
```

打印发现 `shp` 标注缺项后，仅复跑受影响 results / display-units / report-print 三文件 **38/38**；最终 TypeScript/Vite 构建通过。按功能簇验收，没有每步全量回归。

真实桌面浏览器使用同一保存运行，检查 1440×960 / 1024×900 浅深色、全部八阶段、目录与键盘焦点、报告返回运行、复制地址重开、返回时单位保持、长结构化来源的局部滚动及零页面横向溢出。实际字体为 Space Grotesk 标题、Inter 正文，中文为系统回退。浏览器尺寸覆盖和显示单位已恢复。

排队、运行、部分、取消、失败、读取/对比错误和多工作点由组件测试覆盖；没有为这些状态伪造后端保存运行或重复计算。Windows 原生打印对话框、手动按钮与 Ctrl+P 的对话框操作没有验收；已独立验证事件逻辑，并通过 Chromium `Page.printToPDF` 实际触发浏览器打印路径与恢复。

## 真实保存结果与 PDF

隔离匿名预览数据库：`.superpowers/sdd/advanced-workflow-plan-2026-10-04/browser-check.db`。仅新增一次受控基线运行，后续全部复用：

- 项目 `12183063-7d10-427e-94fc-3077331c8af1`，HMS Queen Mary，修订 1，工况 `normal-engineering`。
- 运行 `030f5064-1ef7-497c-92a5-26f1dc7972a3`，completed，八阶段：loading、systems、l0、geometry、equilibrium、hydrostatics、deck、propulsion。
- 总质量 `27851.62934079477 t`，龙骨基准水线高度 `9.088700929185741 m`；GM 保存值为 null，页面保持未知。本轮不承担计算核心正确性或史实认证验收。
- 项目指纹 `a74dff1f47052a363cc14793ec54966e3847f1408ff8abc6e66ee1c951926350`。
- 输入指纹 `f51f140ba7eb4663850006307cf33d2071f201536b97fbecd95cff9b86ac340b`。
- 请求指纹 `e5a81144feb89485da2ed500e65537f6bcbda637dd6b78a2e99f47658662e2a9`。

浅深色各保存一份 A4 PDF，均 **35 页**。第一页身份与单位可读；提取检查覆盖全部八阶段、三个指纹、全部诊断代码/消息/路径/来源路径、六条保存假设，以及 **118 组声明、929 个实际来源路径**，无缺项。来源位于 result.sources、input_snapshot 和已请求阶段数据；结构化声明整体保留，不重复遍历声明内部。

重新渲染最终 PDF，逐页缩略图检查和首/末页、长诊断、功率声明及长来源分页细查无重叠或裁切；深色打印白底。实际打印后，原来打开的附录/来源组仍打开，关闭的仍关闭；默认全部关闭的情形也已检查，原始阶段 JSON 未因打印挂载。受控运行没有阻力长表格、GZ 或破损结果，专项内容由组件测试验证，不将它们声称为本次真实 PDF 证据。

用户可查看的打印样本、实施计划副本与截图保存在本次聊天的 outputs 目录。仓库保留界面证据：

- [1440 报告浅色](assets/run-report-2026-10-06/report-1440-light.png) · [深色](assets/run-report-2026-10-06/report-1440-dark.png)
- [1024 报告浅色](assets/run-report-2026-10-06/report-1024-light.png) · [深色](assets/run-report-2026-10-06/report-1024-dark.png)
- [1024 长来源](assets/run-report-2026-10-06/report-source-1024.png)
- [1440 运行浅色](assets/run-report-2026-10-06/run-1440-light.png) · [深色](assets/run-report-2026-10-06/run-1440-dark.png) · [1024 运行深色](assets/run-report-2026-10-06/run-1024-dark.png)

## 分工与保护边界

按用户 AGENTS.md：Codex 读代码、规划、写 brief、审查、独立验收与记录；OpenCode 在同一会话 `ses_ef2f21aa7ffewFlPKvrj2ULKNI` 顺序实现 A/B/C/D，使用既定 `opencode/space-bunny-free`。A/B 两轮审查后的剩余缺陷由 Codex 接回；C/D 反馈由 OpenCode 补修，最后的单行 shp 标注由 Codex 完成。只读复审无剩余可执行问题；最终浏览器/PDF 由 Codex 验收。

字体文件、许可/README、字体文档、index.html、portfolio.css、tokens.css 等 **11 个保护文件 SHA256 均与第二组开始前一致**。第一组与并行改动保留，不重置、不整体暂存。不改后端、核心、API 或依赖，不做移动端。

下一轮仅规划第三组转场与交互反馈；冻结时再做一次全量前端回归。发布前仍需整合并行字体成果、检查干净检出，并按独立发布任务验收。

> **发布后附记 · 2026-10-06**：本组改动已连同第一组与 Space Grotesk / Inter 字体随提交 `7131a78` 发布上线（`plimsoll-web-20261006T032422Z-7131a78`，站点 https://119.91.211.156）。上文为发布前的实现与验收记录，原文保留。公网验收使用既有项目与既有运行，未新建或修改项目、修订与运行，未改动工程输入；浏览器主题曾切换后经既有 UI/API 恢复为浅色，主题偏好有写入并已还原。**生产原生打印对话框未测试**，上文打印证据仍只来自本地隔离预览。上线事实见 [2026-10-06 生产发布交接](release-2026-10-06.md)。第三组功能转场仍未实施。
