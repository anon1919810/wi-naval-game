# Work/About 圆形揭示与辅助线 · 2026-10-07

本轮基于 `f29b287` 的干净工作树，完成本地实现与 Codex 独立验收。**未提交、未推送、未部署；生产仍为 `0add0b4`。** 不改变 Space Grotesk / Inter、全局字体、工作空间、API、后端、依赖或部署配置，不开展移动端设计。

## v2 设计与行为（后续细化见下文）

两页沿用同一底色，浅色 `#f6f6f3`，深色 `#101110`。旧的零碎尺规、页边小图标已从公共页面撤下。全页共享极浅的制图线与大弧线；Work 在展板信息下方使用一组较大的同心弧、径向刻度、切线与真实交点；About 以较弱底稿搭配一幅复杂的 Lissajous 线图。图中各曲线对应标注的 x=sin(at+φ)、y=sin(bt) 参数，不能被理解为舰船测量。

所有装饰旁注为英文，自托管 Caveat 400–700（附 OFL），正文 Inter / 标题 Space Grotesk 不变。About 图形在宽桌面与介绍并列，在 1024px 桌面移入独立区域。同底色留白保护正文；不靠 z-index 假装线条不会穿字。Work 图形留在 main 内以跟随圆形揭页，工作空间仍使用原有 SiteGeometry。

500ms 圆形从导航预览的位置揭出新页面，旧页面保留在圆外。中性 1px 主边界后跟两道延迟波纹，每道固定 96 个采样点，振幅随进度衰减，精确裁切圆与文字不变形。另有固定 18 个低强度点/短屑。蓝色继续归属字母与下划线；Work 自身被鼠标/键盘预览或点击保持时，01 圆点转为瑞士红 #E2231A、白色数字。About 预览不触发 Work 红点；held 优先级高于 hover/focus，结束后回归当前预览。

点击圆心是鼠标进入字母的位置；键盘为词中心。没有新点击的 Back/Forward 在页面提交和滚动定位后重新测目标词中心，不能复用上次点击。没有有效词框时使用目标可见正文中心。

Work 合成声 540→440Hz / 84ms / 峰值 .05；About 620→500Hz / 124ms / 峰值 .046。统一 200ms 节流，真实手势解锁；只把实际建立的提示声记为已发声，冷 hover 不会吞掉第一下真实点击，已发声的预览点击不重复。静音持久化和音频节点释放保持。

## 实现归属

`circularReveal.ts` 持有几何、RAF 和清理。四层关系为旧正文副本 → 同底色、不透明且圆形裁切的真实新 main → 细边界/粒子 → 真实 chrome。只复制正文，副本 aria-hidden / inert / pointer-events:none，导航引用移除；SVG 图片 href 保留，ID、mask/filter/use 等内部片段引用重命名。

旧层限界为旧正文、目标正文与视口的交集，防止长 About 副本盖住短 Work 页脚。副本偏移保持原来屏幕位置；新 main 裁切坐标使用提交后的真实矩形，圆半径覆盖目标的可见区域，不能追逐屏幕外的长文。结束时恢复原有 clip/background/z-index，页面自身高度不加占位。

`transitions.ts` 保留 generation、取消和完成通知；旧回调不能清掉新转场。`RailNav` 持有预览起点并消费一次点击；`Portfolio` 同步提交页面、恢复滚动与必要焦点。页眉/导航/页脚不复制、不裁切，原有 sticky 导航保持。

滚动导致几何变化、resize、页面隐藏、动态减少动效、焦点进入正文、卸载和更晚导航都会清掉两层、RAF、监听和内联状态。同步路由定位排队的 scroll 事件在几何未变时忽略。减少动态效果和不支持原生 View Transitions 的浏览器立即换页；音效失败不阻断导航。

OpenCode 完成主要实现；两轮审查未通过后按委派约定停止，由 Codex 修正层级、圆心、滚动及 sticky 导航，并更新旧页面切换测试和完成独立验收。

## 本轮细化（同一基线之上的用户修订）

已验收的 v2 交互保持：500ms 圆形揭页、四层关系、点击圆心与历史回退、键盘/reduced-motion、18 粒子与两道波纹、Work/About 提示声。本轮调整版面与文案，并撤下手写旁注；沿用开始时的未提交工作，没有覆盖已有修改。

**Work 制图弧**：`.ff-main` 改为横跨两栏（`grid-area: 2/1/3/-1`），导航仍留在 grid-column 2、层级 z-index 4 之上的真实节点。栅格与正文宽度共用同一对 token（`--ff-rail` / `--ff-gap`），正文区宽 `calc(100% - rail - gap)`；制图场是 `main` 的直接子元素、绝对定位 `inset: 0`，因此取得整幅宽度（含导航列）而不增加高度。焦点 (1180, -60)，主半径 800（相对 1440 宽度），另有 660 / 520 与两条更淡的 980 / 1160 底稿；61 道 3° 径向刻度（每 5 道加长）。下缘弧落在 `.ff-home` 底部新增的 110px 留白内，切线在弧与 DATUM=720 的交点处按真实半径法向绘制。遮挡只用同底色留白（`.ff-home > *` 与 About 阅读区），不给文字加投影遮罩。窄屏 fallback 不变，≤650px 时该留白与投影均撤下。

**About**：保留复杂 Lissajous 主图与真实参数公式，去掉两处手写标语与 Caveat `@font-face`（字体文件保留未删）。新增三节真实舰船研究：01 SCALE（Fr 与 Re）、02 FRICTION（Conn 1953 / Schoenherr 近似 Cf 与 Re 的对数轴图，Re 10⁶–10⁹）、03 POWER（P_E = R_T·V 与 R_T = R_f + R_r）。每节为 `figure` 与文字并列的 grid 项（不是等宽卡片），正文区与绘图区落在同一 12 栏逻辑上，中间一节镜像排布。公式为真实分数/根式/sub/sup 的衬线数学排版（Cambria Math / STIX Two Math 回退栈，28–34px），每个方程包在 `white-space: nowrap` 的 `.ff-equation` 内整体换行，`role="img"` + 撰写好的 `aria-label` 提供可访问名称；无渲染库、无新字体。文案为简洁编辑体：每节正文 ≤30 词、注释 ≤20 词；取消"不外推""不是实测"等辩解式说明，摩擦一节只保留"Shown for 10⁶ ≤ Re ≤ 10⁹"；资料出处压缩为一条 Molland / Turnock and Hudson, *Ship Resistance and Propulsion*, Appendix A3 (after Gertler 1954) 书目，不声称任意页码或公式编号；不主张 Fr/Re 发明归属。三节均为量之间的关系，未虚构任何舰船性能数据。

`--ff-cols` / `--ff-col-gap` 定义在 `.ff-about` 上并被三节复用，保证各级轨道对齐。全局字体、`src/styles/*`、`App.tsx`、leaveGuard、Workbench/Run/Report 与 Library 的 SiteGeometry 均未改动。

### 本轮 Codex 独立验收

- 最终功能簇 5 文件 **108/108**，全量 25 文件 **427/427**，无跳过；`npm run build` 通过（89 模块），`git diff --check` 通过。移除 5 项重复静态文案/结构断言，保留新增的跨列转场回归；修正测试夹具的导航位置。
- 实际浏览器：1440×960、1280×960 浅色及 1024×900 深色无横向溢出；公式以完整方程换行，最右侧 10⁹ 刻度完整。Work 偏心弧在下缘及导航列可见，正文和按钮清楚。
- 实拍中间帧确认圆内 About、圆外 Work，页眉与导航保持真实节点；结束后副本/边界为 0，main 内联裁切清空。长 About 滚动后导航保持 sticky，返回 Work 归零滚动；快速反向与 reduced-motion 均落到最后目标。
- 15 个既有字体/全局样式及工作空间保护文件 SHA256 与开始时一致。没有提交、推送、部署或修改工程数据。
- 本轮截图位于当前任务 outputs：`swiss-work-v3.png`、`swiss-about-v3.png`、`swiss-about-hero-v3.png`、`swiss-about-studies-v3.png`、`swiss-reveal-mid.png`、`swiss-work-dark-1024.png`、`swiss-about-dark-1024.png`。下方旧截图和数字仅属于 v2。

资料核对：已阅读用户本地瑞士风格目录的两份文字与三幅参考图。教材选用及 Appendix A3 来源按 `docs/sps-replacement/PLAN.md` 和 `tools/plimsoll/cases/taylor_gertler_cr_table.json` 记录确认，公式按 `tools/plimsoll/resistance.py` 核对；未重新读取原教材全文。[Cambridge 官方书籍前言](https://assets.cambridge.org/97805217/60522/frontmatter/9780521760522_frontmatter.pdf)核对书名与作者，[ITTC 官方程序](https://www.ittc.info/media/9603/75-02-02-03.pdf)核对 Fr/Re 定义。摩擦图采用项目已有 Conn 近似，不将其误称 ITTC 1957。

## v2 基线验收证据与限制

- v2 装饰重设计功能簇：6 文件 116 项全部通过，新增红点 hover/leave、键盘/reduced-motion、点击保持优先级和波纹有界/衰减/实际绘制检查。
- v2 全量前端：25 文件 **426/426**，无跳过；TypeScript + Vite 构建通过（89 模块）；`git diff --check` 通过。
- 实际浏览器：1440×960 浅色 / 1024×900 深色，无页面横向溢出；圆内新正文、圆外旧正文、中性边界可见。运行中仅一组旧层/边界和18个粒子，唯一 ID 与旧扫描图引用保留；结束全部移除。
- 长 About 滚动后导航仍 sticky，历史返回圆心与提交后词中心一致；快速反向最新目标生效，滚动和 resize 清理，动态 reduced-motion 立即落到真实目标页面。
- 放大镜在左下边缘圆心仍跟随实际指针，外溢由展板裁切，Home/Escape 可用。既有字体/全局样式及 App、Workbench、Run、Report、leaveGuard 共15个保护文件 SHA256 未变。
- 音效只验证参数、手势/静音/节流/节点生命周期；未宣称实际扬声器的主观听感。没有创建工程、运行新计算或验证生产新版本。

可复查命令（仓库的 `web/frontend`）：

```powershell
npm.cmd test
npm.cmd run build
```

仓库根目录执行 `git diff --check`。最新重设计截图存放在当前 Codex 工作区的 `outputs`：`work-redesign-v2.png`、`about-redesign-v2.png`、`wave-redesign-mid.png`、`work-redesign-dark-1024.png`、`about-redesign-dark-1024.png`。旧 desktop 截图对应已被替换的辅助线版本。所有截图均为本地证据，没有部署本次改动。
