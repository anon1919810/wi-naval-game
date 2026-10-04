# Formfield 加载与渲染修正交接 · 2026-10-05

工作树：`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`，分支 `feature/plimsoll-1.0`。

## 保存与范围

首先提交已认可的首页、原图、测试与交接：**`fc71434` — feat: preserve Formfield portfolio homepage**。这是继续优化前的完整恢复点。

本轮随后修正加载、动画更新、滚动和主题，同一分支另行提交。没有修改计算核心、Unity、服务器或生产数据库，没有推送或部署。2026-10-04 交接中的“未提交”与“不等待图片”是历史记录，以本补充说明为准。

用户认可的详细原图继续使用，三个 PNG 的 SHA-256 与既有清单一致；没有再次简化或生成式重绘。

## 改动与决策

| 项目 | 当前行为 |
|---|---|
| 图片门控 | `images.ts` 的 `new Image()`＋`decode()` 预载当前图；解码完成才挂载 Splash，随后完整播放 2500 ms。缺少 decode 的浏览器使用 onload。 |
| 首图与其他图 | HTML preload 首图；当前图就绪后，在首页 idle 预取其余两图。无 requestIdleCallback 时用延时调度。不会等三图齐备才起播。 |
| 缓存与失败 | 当前 Portfolio 实例内按 URL 去重，失败从缓存移除。最多等待 8 秒；失败／超时退出开场、恢复页面，并提示切换参考或 Replay Intro 重试。 |
| 等待体验 | 黑底 PREPARING THE DRAWING，有 Skip Intro；Escape 也可跳过。没有假进度。用户减少动态效果时不进入等待遮罩或动画。 |
| 竞态 | 切换图稿、离开首页或卸载后的旧加载回调不更新状态；StrictMode 不重复创建相同当前图的解码请求。 |
| 滚动 | 等待与开场期间锁定 html/body overflow，结束、跳过、失败、切路由及卸载时恢复原值。Splash 使用 clientWidth/clientHeight，并响应 resize/scroll 重新测量。 |
| Splash | rAF 直接更新 DOM 引用上的裁切、尺寸、变换和阶段属性；没有每帧 setState。进入收整只通知父组件一次。 |
| 展台探索 | 指针输入只更新 ref，以一个 rAF 合并到 DOM 变换和焦点坐标；方向键、Home、Reset view 保留，切图／切页和卸载清理待执行帧。 |
| 浏览器主题 | 公共主题同步 theme-color 与根节点 color-scheme；加入 color-scheme meta。离开公共页面恢复接管前值，不把公共主题强加给 Plimsoll。 |
| 视觉 | 公共主区最大宽度 1460px；深色舰船墨线输出 alpha=0.85，原图与净底曲线不变。字重统一为静态字体常规 400／700，不增加字体下载。 |

初始大展台、2.5 秒斜向扫描、收整角度、原图灰度、几何装饰和公共／工具路由结构均保留。

没有把“SVG 滤镜大概率 CPU 渲染”作为事实：具体渲染路径与低端帧率没有实测。能够确认的是 React 逐帧提交已移除。原图约千像素宽的分辨率上限仍存在，限定桌面主区宽度不能补出原图没有的细节。CSS 450／650 本身合法，但静态字体会匹配可用字重；本轮明确采用 400／700，减少隐式匹配差异。

## 验证

完成上述功能簇后集中执行一次：

```powershell
Set-Location 'C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0/web/frontend'
npm test -- src/__tests__/portfolio.test.tsx --reporter=dot
npm run build
```

- **24/24 通过**，包含此前原图／路由契约、解码前无扫描、StrictMode 去重、完整动画时序、失败／超时释放滚动、旧解码回调、卸载、Escape、reduced-motion 和主题还原。
- React Profiler 测试：连续扫描帧和合并后的多次 pointermove 没有逐帧 React 提交；键盘 Home 恢复原变换。
- TypeScript 与 Vite 生产构建通过；本轮未运行全量计算核心或全套前端测试。
- 浏览器冷缓存：禁用缓存并拦截首图 Image 请求，观察到 `waiting=true / scan=false / overflow=hidden`；放行同一请求后扫描出现，最终 `error=null / overflow=''`。另一次拦截等待触发了超时提示，页面可以继续操作。
- 390×844、320×800 原图布局：页面 scrollWidth 分别为 390、320，未发生横向溢出。检查第一幅及第二／第三幅原稿，核对方向键及 Home 复位。
- 深色主题：DOM 中 theme-color=`#101110`、color-scheme=`dark`、舰船 opacity=`0.85`；返回浅色后同步还原。
- 后端入口：启动本地临时 SQLite 数据库及匿名 API（127.0.0.1:8000），从 Explore Project 经 Vite `/api` 代理进入真实项目库并加载模板；返回首页不重播。未运行 worker、创建舰船或计算，不代表完整业务回归或 PostgreSQL 生产验收。
- 网络拦截、禁用缓存、视口覆盖均已复原，页面留在用户原先的浅色状态。临时 API 验收后停止，前端预览保留。

## 证据与接手入口

证据目录：`docs/formfield/assets/hardening-2026-10-05/`。

- [等待原图](assets/hardening-2026-10-05/cold-image-wait.jpg)
- [390 手机布局](assets/hardening-2026-10-05/mobile-390.jpg) · [320 手机布局](assets/hardening-2026-10-05/mobile-320.jpg)
- [浅色桌面](assets/hardening-2026-10-05/desktop-light.jpg) · [深色桌面](assets/hardening-2026-10-05/desktop-dark.jpg)
- [真实后端入口](assets/hardening-2026-10-05/backend-entry.jpg)

主要源码：`web/frontend/src/portfolio/images.ts`、`Portfolio.tsx`、`Splash.tsx`、`Artwork.tsx`、`VesselDrawing.tsx` 和 `portfolio.css`。入口 preload/meta 在 `web/frontend/index.html`。

## 尚未验证／暂缓

- **实体触屏**：pointer capture 与原生纵向滚动的手势冲突仍需真机检查，桌面窄视口不能代替。
- **低端机性能**：没有 GPU／CPU 滤镜路径、帧率或电量的测量结论。
- **SEO**：未增加预渲染、SSR 或新依赖，本轮保持现有 hash 路由。
- **部署**：没有推送、域名绑定或生产发布。生产发布应另按现有运维流程执行并做公网验收。

实施曾按项目约定委托 OpenCode；其在约五分钟内仍停留于读取且无实现变更，已中止。以上改动由 Codex 接手实现并独立验收，没有采纳未完成委托的结果。
