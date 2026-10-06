# Plimsoll 工作台 · Formfield 设计语言统一 · 2026-10-05

本轮完成项目库重排与计算工作台的共享视觉样式，保存在本地，尚未部署生产。用户指出旧界面缺乏总站的精准、现代与层级感；本轮采用紧凑工作区、细线分隔和明确的操作主次。

后续：2026-10-06 已实现编辑页工作头与输入层级、运行与报告阅读，仍未提交或部署；本文件保留 2026-10-05 的历史记录。最新实际状态见 [第一组交接](workbench-group-one-2026-10-06.md) 与 [第二组交接](run-report-2026-10-06.md)。

## 实现

- 项目库改为左侧上下文、右侧项目清单。英文 `Projects` 承担主标题，功能说明与表单保留中文。
- 已保存项目优先展示。三种基线改为编号行，显示名称、资料状态、简介与建立入口；空白项目表单仍在同一操作区。
- 匿名工作区常驻简短的浏览器身份与备份提醒；完整保存、恢复和项目文档/计算报告的区别放入原生可展开说明。
- 英文标题使用 Space Grotesk，正文使用 Inter，中文使用系统无衬线回退。中性色底、细线直角面板与少量蓝色操作强调延续总站；警告、失败和完成状态保持语义颜色。
- 辅助线只在项目库留白和分隔末端出现，为静态装饰，不承担工程刻度。
- 编辑页工具条可换行，保持中栏最小宽度约束；甲板、重量行拥有局部横向滚动。报告表格继续保留原有滚动容器，打印样式覆盖深色背景与状态色。

新样式在 `web/frontend/src/styles/workspace.css`，通过 `App.tsx` 加载，仅作用于应用根节点或应用包装层；加载/连接失败界面也继承新材料。`Library.tsx` 只调整呈现结构和恢复说明展开方式，不改创建、打开、身份、保存、计算、导出接口。

## 验证

集中执行一次全量前端测试：13 个文件、190 项，189 项通过；1 项说明区测试因两处文案同时匹配而失败。将测试定位收窄到完整恢复段落后，仅补跑该文件，9/9 通过；其余 181 项没有相关代码变更，未重复全量测试。TypeScript + Vite 构建通过。最后补充的包装层高度样式再次构建通过，`git diff --check` 通过。

真实浏览器检查：1440×960 项目库浅深色、实际 Queen Mary 模板创建和打开、编辑页概览；1024×900 破损选择与甲板多列输入均无页面横向溢出。恢复说明可以展开、收起；返回总站后，公共页面仍为其原有字体与浅色背景。浏览器尺寸覆盖已恢复。

本地匿名预览工作区新建一个 Queen Mary 模板用于页面验收；没有启动新的计算运行。运行/报告覆盖依靠共享样式和现有组件测试，未在本轮生成报告 PDF 或重新验证计算数值。未开展移动端设计、后端/核心回归或生产部署。

## 地址与成果

- 仓库：`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`
- 本地项目库：`http://127.0.0.1:5173/#/plimsoll`
- 样式：`web/frontend/src/styles/workspace.css`
- 呈现：`web/frontend/src/App.tsx`、`web/frontend/src/pages/Library.tsx`
- 行为验收：`web/frontend/src/__tests__/anonymous-workspace.test.tsx`
- 预览：[项目库浅色](assets/workspace-2026-10-05/library-light.png) · [项目库深色](assets/workspace-2026-10-05/library-dark.png) · [编辑页浅色](assets/workspace-2026-10-05/workbench-light.png)

并行字体会话的 `index.html`、`public/fonts/README.md`、`portfolio.css`、`tokens.css` 前后 SHA256 一致；字体资产及其文档继续留在该会话的未提交改动中，本轮不纳入。当前预览使用这些已落盘字体；从干净提交独立构建时需同步字体会话成果。

按仓库规则先委派 OpenCode，该次服务在读取阶段发生连接中断，没有产生编辑，已取消；随后 Codex 实施、分组验证与真实浏览器验收，另行完成只读布局审阅。

```powershell
Set-Location 'C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0/web/frontend'
npm.cmd run test
npm.cmd run build
```
