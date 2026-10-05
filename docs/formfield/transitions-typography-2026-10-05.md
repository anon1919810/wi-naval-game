# Y’s Formfield · 桌面转场与字体交接 · 2026-10-05

本轮把已确认的桌面设计落实到本地代码：中央展台、详细俯视原稿、几何蓝图装饰保持原样；公共 UI 统一使用 Archivo 无衬线字体，并加入参考图切换、Work/About 与 Plimsoll 往返的转场。尚未发布到生产服务器。

## 入口与资产

- 工作树：`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`，分支 `feature/plimsoll-1.0`；本轮起点 `eb186f1`。
- 前端：`web/frontend/`；本地预览 `http://127.0.0.1:5173/`。
- 字体：`web/frontend/public/fonts/archivo-latin-var.woff2`，34,928 字节；同目录包含 `Archivo-OFL.txt` 与来源、校验值说明 `README.md`。
- 原稿：`web/frontend/public/portfolio/ship-plan-01.png`、`ship-plan-02.png`、`ship-plan-03.png`。三张内容未改，沿用净底滤镜与俯视裁切。
- 实际浏览器预览：[浅色首页](assets/transitions-2026-10-05/desktop-light.png)、[深色首页](assets/transitions-2026-10-05/desktop-dark.png)、[About](assets/transitions-2026-10-05/desktop-about.png)。

## 字体决定

采用 Omnibus-Type 的 Archivo，取 neo-grotesque 字形、紧凑标题和强弱明确的字重层级，响应“大胆的瑞士国际主义无衬线字体”的要求。这是设计风格的选择，不声称字体产自瑞士。

全局 `--font-sans` 统一入口，公共页面、导航、控件、Splash、SVG 元信息和 Plimsoll 拉丁字符 UI 使用同一族。首页标题 780、About 标题 800、品牌 620/750、导航与多数元信息 620、正文 450。可变字体使中间字重真实生效，不依赖 Windows 合成字重。

字体同源预载、`font-display: swap`，运行时不请求 Google Fonts。只打包 upright、正常宽度的 Latin 子集；中文使用原有系统无衬线回退，代码/JSON 的专用等宽样式保留。来源和 SIL OFL 文本在字体目录，详见 [官方项目](https://www.omnibus-type.com/fonts/archivo/) 与 [源仓库](https://github.com/Omnibus-Type/Archivo)。

## 转场行为

| 操作 | 时长 | 实际行为 |
|---|---:|---|
| 新文档进入首页 / Replay Intro | 2500 ms | 保留黑底扫描、反向切回主题、收整展台；解码就绪才起播。站内返回不重播。 |
| Reference 01/02/03 | 360 ms | 新图先解码，旧图保留；就绪后在展台内作单边斜向切面，逆向选择从另一边切入。 |
| Work ↔ About | 260 ms | 只移动和淡入内容，导航与页脚固定，不建立整页快照。 |
| OPEN PLIMSOLL / 返回总站 | 450 ms | 展台框与工作空间使用同一命名快照组展开/收整；线图与应用内容分别淡出，不拉伸。 |
| 公共主题切换 | 560 ms | 保留以按钮位置为圆心的主题揭示，加入统一取消规则。 |

CTA 改为 `OPEN PLIMSOLL`，直接进入工具。普通点击由 anchor/hashchange 导航；修饰键、中键由浏览器处理。悬停或聚焦只预取模块，不挂载 App、不请求 API。

“已显示”和“正在请求”分开记录。连续选择只接受最后一次请求；点回当前图会撤销待切换请求；失败保持旧图并出现 Retry。换图中收起镜片和游标，结束后恢复探索。About 和工具往返保留参考图、Geometry、Inspect、平移与采样位置；换图或 Reset 明确重置视点。

## 取消与隔离

`src/portfolio/transitions.ts` 统一协调转场，`Portfolio.tsx` 管理页面与请求。新操作先使旧代号失效，再调用 `skipTransition()`。顺序不能颠倒：[MDN skipTransition](https://developer.mozilla.org/en-US/docs/Web/API/ViewTransition/skipTransition) 说明跳过动画仍执行更新回调。

- 旧回调不会再提交；旧 `finished` 不得清理新转场属性。
- 非参考图操作撤销待切换标记，避免按钮与图面不一致。
- 系统主题、Replay、减少动态效果、路由更换、卸载都会清理当前状态。
- 快照只负责绘制，`pointer-events: none` 允许实时按钮接收后续操作。
- 无原生 API 或启用减少动态效果时直接提交终态；减少动态效果下开场不播放。能力检测参考 [MDN startViewTransition](https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition)。
- 工具淡入/淡出使用 `fill: both`，在延迟与结束后保持端点，避免内容先闪现或重新出现。
- 线稿快照带不透明展台底色，新图覆盖旧图，防止透明墨线叠成双影。
- App 只响应应用 hash；退出项目捕获前不切到 Library。卸载后的身份查找、主题保存和退出回调不会再启动请求或改写总站主题。

工具返回后焦点回到 CTA；公共导航仍可见时保留焦点，原内容被隐藏时才转交新标题。MDN MCP 本轮有传输错误，技术核对使用官方 MDN 网页回退。

## 独立验证

集中验证，未在每一步运行回归。

1. `npm test -- --reporter=dot`：12 个文件、161 项。其余 11 个文件的 144 项全部通过（包括本轮增加的参考图用例）；新增转场文件第一次有 3 项因夹具而失败：默认主题并非 System、jsdom 排队的默认 anchor 导航干扰模拟 hashchange、开场最早阶段还没有 Skip 按钮。
2. 修正夹具与 TypeScript mock 类型后，只复跑 `npm test -- src/__tests__/portfolio-transitions.test.tsx --reporter=dot`：17/17 通过。未因此更改其他源代码，未重复全量。
3. `npm run build`：TypeScript 与 Vite 生产构建通过。

证据覆盖其他 144 项测试和 17 项最终转场测试，不能改写成“最后一次全量一次性 161/161”。新测试涵盖预取隔离、普通导航未被取消、捕获前取消、迟到清理、系统/减少动态效果、返回设置与采样、焦点、直接终态、修饰点击、卸载、返回后 401 不 bootstrap、退出捕获前保留项目、迟到主题保存。普通点击先确认未被应用取消，再模拟 hashchange，不用强制导航掩盖按钮失效。

实际桌面浏览器验证：自定义字体已加载，标题计算字重 780；Work/About、工具往返、Back/Forward；斜切与框转场中间帧；展开和返回均为原生 `0.45s`；主题与 `theme-color` 同步；启用减少动态效果并重载后直接显示终态。临时 media 模拟已恢复。

## 边界和复现

本轮未做移动端、低端设备帧率测量、生产发布或后端计算验收。本地 8000 后端未启动；进入工具显示真实连接失败提示，返回正常。不能把前端隔离测试当成端到端计算验收。

原图约 1000 px 宽，仍有大屏和高 DPR 的分辨率上限，本轮没有转换为真正矢量图。下一轮可校准标题尺度、留白、切面方向和墨线密度，再决定是否寻找更高分辨率同源图。

```powershell
Set-Location 'C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0/web/frontend'
npm test -- --reporter=dot
npm run build
```

预览使用 `npm run dev`；已有 5173 服务运行时直接打开预览，勿重复启动。
