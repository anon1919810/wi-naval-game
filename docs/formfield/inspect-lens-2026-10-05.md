# Formfield 桌面端精校记录（2026-10-05，第三轮 · 局部放大）

在 `426370f`（保存已有主题开关与光标）之后进行，**仅桌面端**，只动公共首页的呈现层：Plimsoll 计算功能、路由契约、原图字节与像素增强管线均不变。本轮无后端改动、无 Plimsoll 应用改动、无新增依赖。本地提交保存，未推送、未部署。OpenCode 实现，Codex 审查、修正并独立验收。

## 1. REAL INSPECT：把 90px 装饰标记换成真正的局部放大镜

新增 `src/portfolio/lens.ts`（纯函数映射）与展台内的 `.ff-lens`。

- **复用同一套渲染**：镜头内部是**第二个 `<Artwork>` 实例**（`pixelFrame`），带独立的 `useId` filter/clip id，因此与展台共用同一张原图裁切、同一主题墨色与色调曲线、同一平移/静止角/图板视差；镜头只是把外层 `<svg>` 的 viewBox 收窄到采样点，**不是第二套渲染器**，也不可能凭空多出细节。
- **精确 2×**：镜头内构图保持 1 构图单位 = 1 CSS px（根 `<svg>` 取 1600×700 的像素框），放大比只由外层 viewBox 决定：`span = size / (2 × scale)`。
- **meet/letterbox 映射**：`.ff-exhibit` 是 `aspect-ratio: 16/7; max-height: 620px`，宽屏下高度被钳制后矩形成 16:7 以外的形状，SVG meet 会留左右死边。`samplePoint()` 先算 `scale = min(W/1600, H/700)` 与居中偏移，再把指针的展台内比例换算成构图坐标：`x = (fx·W − offsetX) / scale`（CSS 位置与构图坐标分开保存，避免把像素当单位）。
- **有界**：镜头圆心被限制在展台内（`size/2 … W−size/2`），采样点始终由 viewBox 锁定在放大画面中心。镜内十字保持居中，避免靠边时指向错误细节；展台小于镜头时自动缩小镜头，`pointer-events: none` 不拦截控件。
- **键盘**：Inspect 开启时方向键移动采样焦点（步长 4% 展台宽/高），`Home` 复位采样，`Escape` 退出 Inspect；Inspect 关闭时方向键仍是原来的平移键。展台 `aria-label` 随模式切换说明当前键位。
- **可见性**：镜头在「指针在展台内」或「键盘正在操作展台」时出现；鼠标移动接管键盘模式，之后离开展台会隐藏镜头。键盘失焦也会隐藏镜头，键盘路径不依赖鼠标。普通十字光标只跟随鼠标。
- **reduced motion**：悬停平移被冻结（`still.current` 读一次偏好），但取样与手动检视照常工作。镜头 2× 标记为 `2×` + `REF 0x`，不写任何测量或分辨率承诺。

## 2. TONAL CONSISTENCY：逐张色调档案

`plans.ts` 新增 `TonalProfile { slope, intercept, gamma, opacity }` 与 `sheetTone(sheet, dark)`；开场 Splash、展台、镜头三处共用同一份档案。滤镜仍是「灰度转 alpha → 单条色调曲线 → SourceAlpha 约束 → flood 墨色」，**无模糊、无形态学、无卷积、无边缘检测、无重采样**，原 PNG 字节未改。

> 实现注记：`feComponentTransfer` 同一通道的第二个 `feFuncA` 会**覆盖**而非叠加前一个，所以曲线合并为单条 gamma 函数 `amplitude·density^exponent + offset`（exponent=1 时与原来的 linear 完全等价）。

深色曲线下对原始 PNG 取带区直方图（评估对象是真实像素，非臆造细节）：

| 图 | 中位灰度 | p25 | 深色下墨量均值 | 墨量 ≥0.6 占比 |
|---|---|---|---|---|
| 01 | 255 | 252 | 0.117 | 10.0% |
| 02 | 184 | 45 | 0.340 | 33.7% |
| 03 | 215 | 115 | 0.234 | 13.8% |

02 的问题是**密排深色甲板晕线**铺满整个船体（局部均值灰度 58，58% 像素低于 60），反相后变成一整片近实心亮白甲板——正是用户看到的现象。因此 02 的中间调降幅最大，同时保留最暗原始细节；03 的平灰填充同步缓和；**01 保持现状不变**。

| 图 | light slope / intercept / gamma / opacity | dark slope / intercept / gamma / opacity |
|---|---|---|
| 01 | 1.2 / −0.05 / 1 / 1 | 1.08 / −0.035 / 1 / 1 |
| 02 | 0.72 / −0.02 / 1.35 / 0.9 | 0.95 / −0.02 / 1.8 / 0.95 |
| 03 | 0.92 / −0.02 / 1.15 / 0.92 | 0.92 / −0.03 / 1.2 / 0.9 |

曲线单调、只改墨量不改几何：`gamma > 1` 把中间调压下去而最深墨线仍是最强墨；`opacity` 只在合成层乘系数。02 深色初值过暗，Codex 经浏览器比对把 slope/opacity 提高、gamma 调为 1.8，以保留线芯亮度并抑制中间灰度。**分辨率上限不变**：镜头 2× 不会显示源图里不存在的细节；低于净底阈值的极淡痕迹会被衰减。

## 3. THEME：恢复 System 入口

- 主按钮仍是 Light/Dark 径向切换（reduced motion 或不支持 View Transition 时直接切换）。
- 旁边新增紧凑小按钮 `SYSTEM`：`aria-pressed` 标记是否跟随系统，`title="Follow system theme"`，选择持久化在既有 `THEME_KEY='system'`，并继续监听 `prefers-color-scheme` 变化实时跟随。
- 系统模式下按主按钮切换至相反明暗并退出跟随；跟随状态下再按 `SYSTEM` 则固定当前外观。
- `::view-transition-*` 规则由全局收窄到 `:root[data-formfield-surface='public']`，不污染 Plimsoll 应用。

## 4. CALMER CURSOR

删除 `ff-breathe` 无限呼吸与其 keyframes，保留稳定的蓝图十字准线（描边环 + 十字 + 中心点），Inspect 开启时让位给镜头；`prefers-reduced-motion` 的既有全局兜底保留。

## 5. 涉及文件

- `src/portfolio/lens.ts`（新增）：帧映射与镜头几何纯函数
- `src/portfolio/plans.ts`：逐张逐主题 `tone` 档案与 `sheetTone()`
- `src/portfolio/Artwork.tsx`：`ARTWORK_FRAME`、`pixelFrame`、色调档案接入
- `src/portfolio/VesselDrawing.tsx`：单条 gamma 曲线 + 档案
- `src/portfolio/Portfolio.tsx`：镜头、合帧 rAF 绘制、键盘模式、System 按钮、reduced-motion 冻结
- `src/portfolio/portfolio.css`：镜头样式、静止光标、SYSTEM 按钮、view-transition 收窄
- `src/__tests__/portfolio.test.tsx`：镜头采样（居中/边缘/letterbox/小展台/未测量）、键盘退出与复位、逐张曲线共享、System 持久化与实时跟随、逐帧无 React commit

## 6. 验证

- Codex 对最终代码独立运行 `npm test -- src/__tests__/portfolio.test.tsx`：33/33 通过；`npm run build`：TypeScript ＋ Vite 生产构建通过。发现鼠标接管键盘后镜头残留，修正并补入现有用例后，仅重跑上述相关测试与构建。
- OpenCode 在最后视觉微调前另运行全套前端测试，报告 138/138；最终版本的独立证据以上述 33 项与构建为准。未运行计算核心测试。
- 浏览器桌面实检：三图深浅主题、2× 镜头中心与边缘取样、键盘 Home/Escape、鼠标接管后离开隐藏、System 实时跟随 light/dark 和手动退出。1440×1000 视口下，同一舰船图层的镜内/镜外宽度比约为 **2.000075**（viewBox 舍入误差）。检查完已恢复视口与媒体模拟设置。
- 源 PNG 的 SHA256 与本轮开始一致；无源图修改。未进行低端设备帧率测试。
- 截图：[局部放大](assets/inspect-2026-10-05/desktop-inspect.png)、[02 深色](assets/inspect-2026-10-05/desktop-dark-ref02.png)、[02 浅色](assets/inspect-2026-10-05/desktop-light-ref02.png)、[03 浅色](assets/inspect-2026-10-05/desktop-light-ref03.png)。

## 7. 未做与已知限制

- 本轮**不含任何移动端工作**：无新手势、无移动端 CSS 改版，仅把 `@media (max-width: 650px)` 里指向旧主题按钮的定位选择器改为 `.ff-theme-group`，避免头部布局被本轮 DOM 变化打断。
- 色调档案经桌面浏览器视觉微调；不同原图的填充与纹理差异仍保留。`max-height` 造成的 letterbox 用独立数值预期与 jsdom 断言覆盖。
- 真实触控设备仍未验收；Explore Project 后端链路沿用加固轮结论。
- 开场时序、构图几何、2.5 秒节奏、decode gate、路由隔离均未改动。
