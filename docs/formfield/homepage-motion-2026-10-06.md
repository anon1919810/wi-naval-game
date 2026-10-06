# 首页预览与放大镜 · 2026-10-06

状态：2026-10-07 已随源码 `0add0b4` 提交、推送并部署，公网资源与浏览器验收通过；第三组工作空间改动一并发布。520ms 展板覆片候选已否决并撤回，线上保留 260ms 即时内容切换。发布清单与回滚见 [生产发布交接](release-feedback-2026-10-07.md)。本轮实现基线为 `869f38c`。

执行：Codex 定范围、审查与独立验收；OpenCode 主体实现。两轮审查后仍有快速反向揭示重置问题，按委派约定取消该任务并由 Codex 接回剩余修正、回归及交接。

## 被否决的候选：展板覆片（已撤回）

曾实现并本地验收的 520ms 展板覆片候选已被用户否决，本轮只撤回这一项，其余已验收行为全部保留。撤回范围：`transitions.ts` 的 `COVER_MS` / `COVER_COMMIT_MS` / `COVER_TOTAL_MS` 与 `data-ff-cover` 延迟提交分支、`Portfolio.tsx` 的 `.ff-cover` DOM 与页面切换时的放大镜/光标退出、`portfolio.css` 的 `--ff-paper`、`--ff-cover-*`、`.ff-cover*` 规则与 `[data-ff-cover]` 选择器，以及 `exhibit-cover.test.tsx` 整份测试。已复核运行时代码中不再存在 `ffCover`、`.ff-cover` 或任何延迟提交：Work/About 在设置属性的同一个同步步骤内换入内容。

覆片候选的节拍（220ms 覆盖 / 40ms 停顿 / 260ms 换内容并揭开 / 总 520ms）及其当时的验收事实，保留在本文件下方「历史记录：展板覆片候选」中，仅作历史，不描述当前部署范围。

## 交付行为

- 原生 Work/About 链接仍支持键盘、辅助技术与修饰键新标签打开。`aria-current` 对应已提交页面，预览不会更改当前位置。详情页仍归 Work。
- 字词保留完整排版，蓝色副本径向裁切；进入点固定，最远角确定覆盖半径，300ms 阻尼曲线。途中反向保持实际已绘制圆半径与原点，彻底收回后才能安装新的进入点。下划线使用同一条线变长、变色，短线测量首字母的真实排版宽度，计数徽章不计入词宽。
- 鼠标离开或键盘焦点移出后恢复当前页面；键盘从词中心预览，鼠标点击产生的焦点不会覆盖鼠标原点。点击目标后将蓝色持有到该次转场结束（Work↔About 为 260ms）；取消、重复点击、地址被取代或原生启动失败都释放状态。
- Work/About 为纯内容切换，沿用既有实现：在 `:root` 上设置 `data-ff-page="in"|"out"`，同一个同步步骤内换入内容，260ms 后释放属性，CSS 只对刚出现的分区做 12px 位移加淡入（`ff-content-rise` / `ff-content-sink`）。不截图、不覆盖内容列，页眉与导航不参与动画；页脚仍随文档长度排布。放大镜与自定义光标不再因该切换而退出，只在参考图稿切换时退出。
- 工作空间内部页面之间为 `app-route` 220ms 局部 CSS 揭示，同样不截图长正文；转场的开始/结束、generation 与取消均通过 `onTransitionEnd` / `transitionGeneration` / `cancelTransitions` 通知与守卫，reduced-motion 与不支持原生 View Transitions 时立即换入并同样广播结束。
- 音效是原创正弦下滑音，620→520Hz、110ms、峰值 gain 0.05，经低通与柔和起落；140ms 节流，无文件下载。首次 hover 静音，真实点击或按键解锁，冷启动后点击取消静音也当场解锁。静音持久化；自然结束、静音、卸载或部分建图失败均释放节点。音频被拒不影响视觉和导航。
- 放大镜圆心不再被半径限制在展板内部。跨边缘时圆框被展板裁切，十字和同一渲染图稿的 2× 映射继续跟随鼠标；十二道中性径向刻度与双圈装饰。既有箭头、Home、Escape、绘图控件与参考图稿行为保留。
- reduced-motion 下无预览插值与页面切换延迟；不支持原生 View Transitions 的环境沿用直接换页降级。

## 独立验证

在 `web/frontend` 执行：

```powershell
npm.cmd test -- src/__tests__/page-cut.test.tsx src/__tests__/portfolio.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/portfolio-content.test.tsx src/__tests__/nav-preview.test.tsx src/__tests__/preview-audio.test.ts
npm.cmd test
npm.cmd run build
```

功能簇 6 文件 125 项通过，全量 24 文件 393 项通过，TypeScript/Vite 构建通过。新增测试覆盖实际部分圆半径反向、外部键盘焦点、整次 260ms 切换期的状态持有、启动失败降级、冷启动解锁、音效节流与部分节点清理，以及页面切换的立即换入、260ms 释放、被取代/被取消/卸载时的清理与「覆片不复存在」断言（`page-cut.test.tsx`）。根目录 `git diff --check` 通过。

真实浏览器验收：

- 1440×960 与 1024×900 浅深色，无横向溢出，Space Grotesk / Inter 实际字体正确。
- 1440 快速离开和反向进入采样圆半径约 300→99→103px，原点保持不变，没有跳回零。
- 1024 深色 Work/About 采样：内容在设置属性的同一帧换入，`data-ff-page` 约 260ms 后消失，无任何纸色覆层；1440 正向同样如此。覆片的三阶段采样属历史记录，见下。
- 原生浏览器 Back/Forward、关闭前快速点击返回、从导航外 Shift+Tab 进入、放大镜箭头/Home/Escape。四边四角的圆心均对应实际指针；边缘保留 2× 映射。
- 持久静音后重载，取消静音的真实点击创建音频上下文；实际节点创建与自然结束断连已检查，静音后 hover 不建节点。没有对主观听感或所有扬声器作结论。
- 动态 reduced-motion 后，页面切换计算样式为 `animationName: none`，导航为 `transitionDuration: 0s`，点击立即到达页面。
- 字体资产、tokens、workspace、App、leaveGuard、Workbench、Run、Report 等 15 个保护文件与本轮开始的 SHA256 一致。

证据位于本会话 `outputs/`：`homepage-lens-edge-1440.png`、`homepage-about-1024-dark.png`、`homepage-work-1440-dark.png`。`homepage-preview-cover.gif` 与 `homepage-final-motion/` 属历史覆片候选证据，仅供追溯。逐帧原图与时序保存在 `homepage-final-motion/`。本地预览 `http://127.0.0.1:5173/#/work`。

## 范围

本地实现与验收阶段只涉及桌面公共首页、本地偏好与相应测试；未改后端、API、计算核心、字体、依赖或导出，当时没有启动新计算或触碰生产站点。已有工作空间第三组不在本次重新实现范围；工作空间共享元素或遮罩深化尚未实施。移动端及低端设备帧率未验收。2026-10-07 的生产发布与公网验收另见 [生产发布交接](release-feedback-2026-10-07.md)。

## 历史记录：展板覆片候选（已否决，已撤回）

> 以下为**被否决候选**的实现与验收记录，原文保留以供追溯。它描述的是一个 520ms 展板覆片，**不是当前部署范围**：该候选已从源码与测试中撤回，Work/About 现为上文所述的 260ms 纯内容切换。文中测试与浏览器结论均为当时事实。

- 展板覆片只在 Work↔About 间使用。220ms 中性纸色从一侧铺满内容列，停顿 40ms，在 260ms 同步换内容并揭开 260ms，总长 520ms；返回方向相反。长 About 在同一帧已被覆盖，不从短 Work 下方提前露出。页眉和导航不参与动画；页脚仍随文档长度排布。放大镜与自定义光标在遮罩开始时退出。

历史验收命令（当时的文件集）：

```powershell
npm.cmd test -- src/__tests__/portfolio.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/portfolio-content.test.tsx src/__tests__/nav-preview.test.tsx src/__tests__/exhibit-cover.test.tsx src/__tests__/preview-audio.test.ts
```

历史测试事实：功能簇 6 文件 127 项通过，全量 24 文件 395 项通过，TypeScript/Vite 构建通过；`exhibit-cover.test.tsx` 覆盖 220/40/260 节拍、覆片延迟提交、取代与取消。1024 深色反向覆片采样：旧 About 保留到全覆盖，新 Work 随揭开出现，状态在约 520ms 后释放；1440 正向也采到旧页、全覆盖、新页三阶段。动态 reduced-motion 后覆片计算样式为 `animationName: none`。该文件与 `homepage-preview-cover.gif` 一并已删除或标注为历史。
