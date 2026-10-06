# 工作空间 Transition 与 Loading 实施计划

> 执行约定：Codex 规划、审查与验收；OpenCode 实现。导航保护两轮审查未通过后由 Codex 接回。用户已在本会话确认设计并授权开始。按功能簇集中测试，不逐步运行全量回归。

**Goal:** 工具区的读取、提交、后台计算和失败都有真实且可恢复的反馈；转场说明位置变化并保留草稿和操作能力。

**Architecture:** 共用轻量读取占位组件；业务页面分别拥有请求状态、重试与过期响应保护。局部 CSS 动效不重建 Workbench，页面转场复用现有控制器的同步提交和 latest-wins 规则。离开保护在页面切换和动画前执行。

**Tech Stack:** React 19 / TypeScript / Vite / Vitest / CSS / 已有 View Transitions 控制器，不增加依赖。

**Spec:** 本会话已确认的设计，以及 `next-workspace-design-2026-10-05.md` 第三组。以源码而非原始提案历史基线为准。

## 全局约束

- 标题 Space Grotesk、正文 Inter，保留现有字体资产和全局视觉；仅桌面 1440×960、1024×900，浅深色。
- 不改后端、计算核心、API 契约、匿名身份语义、规范单位或导出；不移动端、不新增动画库。
- 数据就绪立即可用，不以最短 loading 时长或网络等待阻塞转场。
- queued/running/completed/partial/canceled/failed 与取消请求严格区分；无虚构进度、ETA 或阶段。
- 本轮先本地实施验收，文档记录真实状态；不把本地成果描述为已上线。

## 审查重点

- 快速切换、重试、离开后的旧请求不得覆盖新页面或创建额外身份。
- 保存期间继续编辑，新增修改保持 dirty；409 复制草稿与重载路径保留。
- 离开取消后草稿、章节、焦点和地址正确；确认后一次导航；章节/Trace 不提示。
- API 故障和懒加载模块故障必须停止假等待，并能重试/返回。
- reduced-motion、键盘、报告定位、打印保持可用，不动画整个长报告。

## 功能簇一：读取、提交与恢复

**Files:** `src/App.tsx`、`src/pages/{Library,Workbench,Run,Report}.tsx`、新建专用读取反馈组件，`src/styles/workspace.css`；相关 Vitest。

- [x] 共用读取反馈：按 library/workbench/run/report/workspace 匹配结构的细线占位，真实对象文案，role=status 与 aria-busy。装饰占位约 150ms 后显示，快请求避免闪烁；两秒补充等待对象，卸载清计时，不延迟结果。
- [x] Library 将读取失败与创建失败分开；读失败结束骨架、计数不得继续显示读取中，可原地重试，创建入口仍可用。空白创建显示建立中。
- [x] App、Workbench、Report 提供显式原地重试及返回；请求有 generation/active 保护。App 重试先确认现有身份，保持 bootstrap single-flight，不自动重试写请求。
- [x] Workbench 操作状态分为 saving/starting/reloading，保存中不误标运行忙碌；保持保存过程中新增草稿与冲突语义。
- [x] Run 复用读取反馈，保留现有轮询失败时的旧结果和取消错误；活动标记对应真实后台状态，并覆盖 reduced-motion。
- [x] 测试原故障、重试恢复、晚响应、保存期间编辑、操作文案、真实运行状态。

## 功能簇二：转场与离开保护

**Files:** `src/portfolio/{Portfolio,transitions}.tsx/.ts`（按实际后缀）、`src/components/{ProjectNav,InputTrace}.tsx`、App/Workbench、专用导航保护或局部动效辅助文件；相关 Vitest。

- [x] 章节 150ms 淡入/至多 4px；工作头与索引固定，同章节不重复播放。不以 key 重挂持有草稿或当前表单的容器。
- [x] Trace 内容展开/更换字段 180ms；输入值更新不逐键触发动画。不额外夺取焦点，窄桌面仍在流内。
- [x] Library→Workbench 与 Run→Report 220ms；页面身份上下文接续、进入内容轻淡入。优先复用现有控制器，长报告正文不做整体截图变形。不等待 API，unsupported/reduced-motion 立即提交；最新切换获胜并清理。
- [x] dirty 导航保护覆盖返回项目库、公共站点、其他项目、浏览器返回/前进与刷新。确认在转场前；取消保持草稿和当前页面；离开后清理保护。排除章节、Trace、单位与报告锚点导航。避免 Portfolio 与 App 双重提示。
- [x] Splash 本浏览器会话自动一次，明确 Replay 可重播；sessionStorage 不可用时正常降级，保持图片解码与失败恢复。
- [x] 懒加载工具模块 ErrorBoundary 可重试/返回；失败后以真实页面重载获取新文档，正常公共路由不被错误边界锁死。
- [x] 测试 dirty 取消/确认、back/forward、reload、章节及 Trace 保留输入、模块恢复、session intro、动态效果关闭与快速切换。

## 集中验收与记录

- [x] OpenCode 完成功能簇后运行 `npm test -- --reporter=dot` 与 `npm run build`（目录 `web/frontend`），不提交/推送/部署。
- [x] Codex 独立阅读全部 diff，重新运行同样测试和构建、`git diff --check`。
- [x] 本地真实浏览器验证两种桌面宽度、浅深色、慢读取/失败/重试、键盘、连续导航、未保存离开、reduced-motion；复用已有保存结果，不为动效新跑计算。
- [x] 更新 CHANGELOG 和第三组状态，明确本地验证/未上线，并保存简短交接及截图。记录任何未能验证的限制。

验收结果：21 文件、353 项测试通过，TypeScript/Vite 构建与 diff 检查通过。浏览器证据、分工及限制见 [第三组交接](transition-loading-2026-10-06.md)。模块重试改为真实重载，是浏览器失败导入缓存所需的实现修正。
