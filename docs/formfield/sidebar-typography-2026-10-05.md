# Y’s Formfield · 右侧导航与桌面排版 · 2026-10-05

本轮完成公共页面的桌面布局改版：Work / About 移到右侧常驻大字导航，页眉只保留品牌与主题控件。起点 `4f5be47`；本地预览 `http://127.0.0.1:5173/`，尚未部署。

## 当前设计

- 两列网格：展台 `minmax(0, 1fr)`，右栏 `clamp(230px, 20vw, 320px)`，间距 `clamp(40px, 4vw, 88px)`。展台铺满自己的列；页眉、页脚跨两列。
- 右栏字号 74–110px、字重 700、行高 `.86`、字距 `-.025em`。视觉小写，可访问名称保持 `Work 01` / `About`。`01` 表示当前一件作品。
- 圆形徽标作为独立 flex 项，不换行；删除多余右侧预留宽度。悬停 / 聚焦展开字下的强调色细线，当前项保留短墨线，键盘轮廓仍可见。
- 导航在 `.ff-main` 之外，切换 Work / About 时保持位置和焦点；开场期间 `inert`，加入原有收整揭示。2500ms 开场、图片解码门控、参考图、镜片与工具转场逻辑保持。
- 正文正常字距；标题 `-.02em`，品牌 `-.015em`，微标签 `.05em`，CTA `.02em`。移除原来整页的负字距。
- 651–1100px 的桌面窗口允许控制组换行，侧栏仍在右边。650px 以下保留最低限度兜底，未开展移动端设计或验收。

## 最新字体决定与并行工作

用户在本轮确认最新组合为 **标题 Space Grotesk、正文 Inter**，取代先前的 Suisse Int’l 选择。另一会话同时在此工作树接入字体；本轮保留其字体文件、`tokens.css`、预载和字体来源文档，不替它提交。

当前工作树公共 `.ff-shell` 使用局部 `--font-display` 与 `--font-sans`，Plimsoll 应用仍使用自己的 Archivo 令牌。浏览器 CDP 实测：导航为自定义 Space Grotesk 字体，说明段落为自定义 Inter 字体；不是只写了 CSS 名称的回退预览。来源、许可与校验值见 `web/frontend/public/fonts/README.md` 和并行的 [字体交接](fonts-inter-space-grotesk-2026-10-05.md)。

版本保存按职责分开：本轮提交布局与字距调整；字体接入相关的 CSS 声明、字体资源、预载与字体文档留给另一会话。布局提交单独检出时仍采用已有字体，最终组合需包含字体会话的提交。

## 验证与证据

根代理独立集中执行一次针对性验证：

- `npm run test -- src/__tests__/portfolio.test.tsx src/__tests__/portfolio-transitions.test.tsx`：2 文件、56/56 通过，既有测试未改。
- `npm run build`：TypeScript 与 Vite 生产构建通过。
- 源代码检查后修正页脚未跨列、徽标多余占宽和窄桌面侧栏位置；未触及计算核心、后端、Unity 或服务器。
- 实际桌面检查 1024、1280、1440：没有横向溢出；1440 下展台约 1020px、右栏 288px，页脚跨至页面右边。Work / About 切换后焦点保留在侧栏；主题、参考图切换与检查模式可操作。

预览：[浅色首页](assets/sidebar-2026-10-05/desktop-light.png) · [深色首页](assets/sidebar-2026-10-05/desktop-dark.png) · [About](assets/sidebar-2026-10-05/desktop-about.png)。截图包含已确认的并行字体接入。

本轮不把前端验证表述为后端计算验收。原稿资产与转场控制器未修改；字体并行工作仍需其所属会话保存。

```powershell
Set-Location 'C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0/web/frontend'
npm run test -- src/__tests__/portfolio.test.tsx src/__tests__/portfolio-transitions.test.tsx
npm run build
```
