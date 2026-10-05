# Y’s Formfield · 项目详情与作者联系 · 2026-10-05

本轮完成公共页面的作品详情与作者联系：新增 `#/work/plimsoll` 详情页、重做 About（作者 / Built With / GET IN TOUCH），首页在保留直接进入工具的同时增加次级 “VIEW PROJECT”，并实现首页与详情之间 400ms 的共用图稿转场。只改公共壳层；未触及计算核心、后端、Unity、部署、依赖或锁文件。

## 路由与所有权

`src/portfolio/routes.ts` 增加 `PublicView = 'home' | 'about' | 'project'` 与 `PUBLIC_WORK_DETAIL_HASH = '/work/plimsoll'`。

详情是**整路径精确匹配**，置于所有首段规则之前；`#/work` 仍是展台，`#/work/plimsoll/extra` 回落 Work 而不是命中不存在的详情。`#/plimsoll`、`#/projects…`、`#/runs…`、`#/reports…` 全部仍归应用，测试逐条锁定。

## 内容

- **详情**：BACK TO WORK、大号标题、共用图稿 hero、OPEN PLIMSOLL，随后 01 Overview / 02 Capabilities / 03 Workflow（含真实报告截图）/ 04 Technology / 05 Methods & Limits。平面行 + 分隔线 + 现有强调色，无卡片墙。
- **技术栈按 manifest 核对**：React/TypeScript/Vite；Python 计算核心；FastAPI 提供应用、SQLAlchemy 管理存储、Alembic 版本化数据库 schema；PostgreSQL；独立 worker。
- **诚实边界集中在 Methods & Limits**：非完整 SPS 复现、非认证设计工具、破损仅为连通准静态（无穿甲/爆炸/CFD）、完整耐波性/结构强度/历史造价/战斗损伤模拟不在范围、输入含估算与缺项、锁定重心代理不得驱动无自由液面进水、结果绑定其修订与工况指纹。
- **About**：作者 Yang Duanming、tools/experiments 方向、Built With（SVG/CSS 框架与构图线为装饰性合成，非实测工程数据；参考图为归档扫描本身，未重绘/描摹）、GET IN TOUCH。

**COPY EMAIL 只在 `writeText` 真正 resolve 后显示 COPIED。** API 缺失或 reject 一律显示 NOT COPIED，并指向始终可用的 `mailto:` 链接；不做联系表单（此站无后端可接收）。

## 资产

`web/frontend/public/portfolio/plimsoll-report.jpg` 是 `docs/plimsoll-1.0/evidence/public-report-2026-10-04.jpg` 的逐字节副本（41094 字节，856×751，SHA-256 `790e2a70…5e61`），2026-10-04 公网验收时的真实报告截图，无凭据或个人信息，未裁剪未修饰。页面正文不出现任何文件路径；出处记录在该常量注释与 `public/portfolio/PROVENANCE.md`。图注：“A real Plimsoll report, captured on 4 October 2026. Display units can be changed without recalculating. The report retains its validation limits.”

## 转场

`transitions.ts` 新增 `detail` 类型与 `TRANSITION_MS.detail = 400`，走既有快照控制器，因此自动继承特性检测、reduced-motion 回退、无未处理拒绝与 latest-navigation-wins。`content.css` 作用域内：

- `ff-artwork` 命名**当前可见**的 `.ff-art-scene`。详情与 About 仅在可见时挂载——保留隐藏副本会在文档中放入第二份完整图稿（第三个命名候选、第三个 filter id、多余 `img`），这也确实打破了三条既有契约。
- 详情正文另成一组 `ff-detail-body` 升起 400ms；常驻页眉、右栏、页脚在 `.ff-main` 之外，从不被命名、不移动。
- 首页退出按钮 `↖ Y’s Formfield` 指向访客实际离开的公共页；离开展台时记录其滚动位置，任何路径返回首页都恢复原位，其余页面各自从顶部开始。
- 主题按钮、SYSTEM、系统主题与 reduced-motion 的变化，会先退休旧动画并立即提交当前 URL 所请求的页面，防止取消快照后出现地址与画面不一致。另有 4 个延迟捕获回归案例锁定这个行为。
- 长页右栏使用 sticky；公共页预留滚动条宽度；复制按钮的样式优先级高于公共按钮重置。页脚新增安静的 CONTACT 邮件入口。

## 验证

Codex 独立执行，目录 `web/frontend`，2026-10-05 20:21（Asia/Shanghai）：

- `npm.cmd test`：13 文件、187/187 通过，耗时 15.82 秒。既有测试未改。
- 最终复核发现同一工具入口重复点击的取消边界，修正后补跑相关三文件：83/83 通过（20:27），并再次通过构建。没有重复无关的全量测试。
- `npm.cmd run build`：`tsc -b && vite build` 成功。
- 开发服务器实测：`/portfolio/plimsoll-report.jpg` 返回 200 `image/jpeg` 41094 字节；`content.css` 服务正常。
- `git diff --check` 无空白错误；原报告与公开副本 SHA-256 一致。

新增 `src/__tests__/portfolio-content.test.tsx`（27 项）覆盖精确路由与应用 hash 所有权、详情内容与真实截图、无 API 深链、共用图稿转场与唯一命名、探索状态与滚动保持、Back/Forward、被取代切场的退役、主题/系统偏好中断、焦点归属、工具往返与重复点击、reduced-motion 与无 View Transitions 降级、联系成功/失败/无 API 三种剪贴板结果。冻结后只执行一次常规全量前端回归；新增中断用例先单独复现了 4 项失败，再统一验收修复。未运行与本轮无关的求解器或后端全量测试。

## 浏览器证据与本地连接恢复

Codex 使用已打开的 in-app browser 检查 1440×960 与 1024×900 桌面：浅/深色详情、详情冷启动深链、长页侧栏、邮箱复制反馈、OPEN PLIMSOLL 实际项目库、从工具返回原详情。动画结束后均无横向溢出；直接详情与工具返回均无自动开场。1440 长页底部侧栏距顶部 32px，复制按钮有 1px 边框与 16px 内边距。原生系统剪贴板内容未独立读取确认；测试验证 writeText 参数和成功/拒绝结果，浏览器确认反馈。

证据目录：`docs/formfield/assets/content-2026-10-05/`，包含 `detail-light.png`、`detail-dark.png`、`about-desktop.png`、`about-contact.png`、`workspace-restored.png`。桌面 viewport 临时覆盖在验收后恢复。

用户截图的连接错误：Vite 正常但 8000 无 API 监听，代理的 `/api/auth/config` 返回 502，应用因此停在工作空间错误提示。已启动仅监听 127.0.0.1:8000 的匿名本地预览，复用既有隔离 SQLite `browser-check.db`；没有建库、create_all、迁移或重置。`/api/health` 与 `/api/auth/config` 经 5173 代理均返回 200，真实浏览器进入本浏览器项目库。这里只验证入口与返回，没有新增项目或启动计算；旧邮箱身份下的数据没有被迁入匿名身份。

临时预览脚本与日志在被 Git 忽略的 `.superpowers/sdd/local-preview-2026-10-05/`；API 进程当前运行，退出后需用现有后端 Python 环境重启其中的 `anonymous_api.py`。此脚本不是部署入口；生产环境和服务器未变更。

## 版本控制与实现分工

OpenCode 完成第一轮多文件实现；Codex 负责范围、事实核对、浏览器检查和独立测试。两轮反馈后仍有路由取消与样式遗漏，已按委派规则取消委派并直接完成剩余修复。最终验收以上述 Codex 证据为准，不使用委派自己的测试报告作为交付依据。

本轮文件保存为独立本地提交。另一个会话的 `index.html`、字体资产/说明、`portfolio.css` 与 `styles/tokens.css` 改动保留在工作树，不纳入本轮提交。当前预览使用用户确认的 Space Grotesk 标题与 Inter 正文；字体本身仍由另一个会话收尾。未推送、未部署；未做实体移动端验收。

参考官方 [MDN View Transitions](https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition)、[view-transition-name](https://developer.mozilla.org/en-US/docs/Web/CSS/view-transition-name) 与 [Clipboard.writeText](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText)。本次 MDN 连接器传输不可用，使用官方网页作为备选。

```powershell
Set-Location 'C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0/web/frontend'
npm.cmd test
npm.cmd run build
```
