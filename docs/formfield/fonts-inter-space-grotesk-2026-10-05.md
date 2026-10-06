# Y’s Formfield · Inter + Space Grotesk 字体包交接 · 2026-10-05

本轮把公共外壳的字体从“名义上的 Suisse Int’l、实际回退系统字体”落地为两个自托管可变字体：正文 **Inter**，展示标题 **Space Grotesk**。均为 SIL OFL 1.1，可合法自托管与随应用分发。工作树 `C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`，分支 `feature/plimsoll-1.0`，未推送远端、未发布生产。

## 资产与声明位置

- 字体文件：`web/frontend/public/fonts/inter-var-latin.woff2`（48,256 B，`wght` 100–900）与 `space-grotesk-var-latin.woff2`（22,288 B，`wght` 300–700），均只含 Latin 子集，与既有 Archivo 的单子集策略一致。
- 许可全文：同目录 `Inter-OFL.txt`、`SpaceGrotesk-OFL.txt`；来源 URL 与 SHA-256 校验值记录在同目录 `README.md`。
- `@font-face` 声明：`src/styles/tokens.css`，紧随 Archivo 块之后，`font-display: swap`，`unicode-range` 与 Google Fonts 的 `latin` 块逐字一致。
- 预载：`index.html` 在 Archivo 之后加两条 `<link rel="preload" as="font" crossorigin>`。

## 接入方式

`portfolio.css` 的 `.ff-shell` 内部重定义两个令牌，不影响 Plimsoll 应用自身的 Archivo 令牌：

- `--font-sans: 'Inter', …系统回退` —— 正文、导航元信息、控件、页脚等全部默认文本。
- `--font-display: 'Space Grotesk', 'Inter', …系统回退` —— 展示标题：`ff-wordmark`、`ff-rail a`（Work/About 大字导航）、`ff-work-heading h1`、`ff-about h1`、`ff-about-work h2`。

原先注释里“Suisse Int’l 为目标字体但不打包”的表述已删除：现在的字体栈只声明实际发货的字面。中文继续走系统 CJK 回退，不打包 CJK 网络字体。

## 验证

- `npm test`：12 个文件 161 项全部通过；`npm run build` 通过。
- 本地预览 `http://127.0.0.1:5173/` 截图验收：[浅色首页](assets/fonts-2026-10-05/desktop-light.png)，标题为 Space Grotesk、正文为 Inter；两个 woff2 经 dev server 直接 GET 均为 200。

## 后续可调

- Space Grotesk 最大字重只有 700；若标题想要更重的海报感，只能换字体，不能加 `font-weight` 数值（浏览器会合成假粗体）。
- 若 About 页日后出现拉丁扩展字符（重音符号等），需按 `README.md` 里的同一来源补 latin-ext 子集文件。
