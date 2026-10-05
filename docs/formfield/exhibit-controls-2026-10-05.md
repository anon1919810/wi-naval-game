# Formfield · 展板控件与全站辅助线 · 2026-10-05

本轮已实现并验证，保存在本地；没有部署生产。延续中央展台、详细俯视原图、Space Grotesk 标题与 Inter 正文、浅深色主题及 2.5 秒开场。

## 本轮行为

- 撤下作品信息下方的独立工具栏。展板左上是 Inspect 图标，左下是 01 / 02 / 03 切换，右下是 Reset view；各按钮保留 44px 点击区域、键盘与辅助技术标签。
- 辅助线始终显示，取消 Geometry 开关。作品标题、副标题和 OPEN PLIMSOLL / VIEW PROJECT 保留为独立的信息与操作层。
- 按钮的 pointer 与键盘事件不会触发展板平移、指针捕获或放大镜跟随。进入控件或聚焦控件时撤下跟随镜头；展板本身仍支持方向键探索和 Home 重置。
- 图片解码、切换失败保留旧图、重试、转场取消以及返回首页的视图状态继续沿用已有实现。错误提示归入展板，并限制高度以避免窄桌面裁切反馈。

## 装饰语言

新增复用的 `SiteGeometry`，用细刻度、圆与十字定位、斜向构成线延续展板语言。放置于 About 留白、作者与技术段落分隔、作品详情章节分隔和公共页脚；不进入 Plimsoll 工作台。

装饰使用主题变量、低对比静态 SVG，`aria-hidden`、不可聚焦、`pointer-events: none`。这些是图形构成，不是测量、比例尺或舰船工程数据。没有额外鼠标动效或每帧 React 状态更新。

布局补充样式集中在 `web/frontend/src/portfolio/exhibit.css`，不编辑并行字体会话使用的 `portfolio.css`、`tokens.css`、`index.html` 和字体文件。四个已有字体改动文件在本轮前后 SHA256 一致；本轮提交不包含它们。

## 验证与边界

最终分组验证（2026-10-05 21:03，本机时间）：

```powershell
cd web/frontend
npm.cmd run test -- src/__tests__/portfolio.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/portfolio-content.test.tsx
npm.cmd run build
```

结果：3 个测试文件、85 项通过；TypeScript 与 Vite 构建通过。新增验证覆盖控件位置、辅助线常开、按钮 SVG 事件隔离、键盘与放大镜行为。审阅后修正了装饰插入导致的页脚子元素次序变化，以及错误提示高度边界。

真实浏览器检查：首页浅深色、Inspect 键盘探索与 Reset、02 切换、About、详情章节、1024px 桌面无横向溢出；保存 1440×960 预览后恢复浏览器原尺寸。按用户范围未进行实体移动端测试，也未跑后端或计算核心回归。

按仓库规则先委派 OpenCode；该次委派持续停留在读取阶段，没有产生编辑，已取消。随后 Codex 完成本轮实施与独立验证。没有等待中的本轮委派任务。

## 地址与资产

- 仓库：`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`
- 本地首页：`http://127.0.0.1:5173/#/work`
- About：`http://127.0.0.1:5173/#/about`
- 详情：`http://127.0.0.1:5173/#/work/plimsoll`
- 组件：`web/frontend/src/portfolio/Portfolio.tsx`、`SiteGeometry.tsx`、`AboutContent.tsx`、`ProjectDetail.tsx`
- 样式：`web/frontend/src/portfolio/exhibit.css`
- 原图：`web/frontend/public/portfolio/ship-plan-01.png`、`ship-plan-02.png`、`ship-plan-03.png`，本轮未修改。
- 预览：[首页浅色](assets/exhibit-2026-10-05/home-light.png) · [首页深色](assets/exhibit-2026-10-05/home-dark.png) · [About 装饰](assets/exhibit-2026-10-05/about-geometry.png) · [详情装饰](assets/exhibit-2026-10-05/detail-geometry.png)

后续视觉精校可调整装饰对比、分隔线末端密度与展板图标力度，先由本地预览确认。生产仍为此前 Plimsoll 版本，本轮没有发布。
