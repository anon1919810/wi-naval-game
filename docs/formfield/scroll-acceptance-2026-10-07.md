# Portfolio scroll · 本地验收交接

日期：2026-10-07，Asia/Shanghai。基线 `44dec6c`；本轮未提交、未推送、未部署，线上仍为此前发布。

设计见 [执行计划](../superpowers/plans/2026-10-07-portfolio-scroll.md)。OpenCode 实现主体，Codex 审查、修正控制器和 React/CSS 整合后独立验收。另一次只读审查发现的指针/键盘混用导致链接消失问题已修复并补回归测试。

## 已实现

- 两处 Plimsoll H1 均是 `#/plimsoll` 的真实链接，保留懒加载预取、原工具转场、返回来源与焦点恢复。装饰副本不进入无障碍名称；标题仍读为 Plimsoll，链接读为 Open Plimsoll。
- 300ms 圆形文字预览和下划线；瑞士红仅落在原 i 点。View Project 是标题之外的次级链接，整个标题、间隙和操作共用悬浮/焦点区域；二者都离开后延迟 140ms 关闭。修改键和中键交给浏览器。
- 图标化声音、手动主题、重播；旧 SYSTEM 偏好回退浅色，公共站点不订阅系统深浅变化。
- 详情 H2 在章节内停驻于视口顶端 32px；阅读刻度是主导航旁的独立 navigation landmark，按真实章节间距布置，跳转目标使用 96px 阅读线并聚焦 H1/H2。
- 章节切换使用 24px 滞回、140ms 停稳；用户操作短时授权声音，程序定位/重排/隐藏恢复会清除待播放声音。刻度显式跳转绕过滞回，支持小数布局坐标及页末章节。
- Work 大弧的旋转/错位使用固定容器测量，避免测量自身变换产生反馈。About 谐波轨迹、Cf/Re 游标均由原方程计算；尺度和功率图案使用有界强调。运动仅查询真实 main 内的图，不触碰圆形揭页的旧页副本。
- 单一 requestAnimationFrame 队列，420ms 有界收尾；隐藏时停止，非主图冻结；减少动态效果保留完整静态图和公式。

## 验证

在 `web/frontend` 执行：

```text
npm.cmd run test -- --reporter=dot
28 test files passed · 496 tests passed · 0 skipped
npm.cmd run build
TypeScript passed · Vite 95 modules
```

仓库根目录 `git diff --check` 通过。全量日志：当前 Codex 任务目录 `outputs/scroll-acceptance-tests.log`。测试输出包含预期的错误边界模拟日志，以及既有 nav-preview 测试的 act 提示；无失败或跳过。

浏览器实测：

- 1440×960：标题蓝字/红点/下划线，展开入口，About 8 个刻度和详情 5 个刻度均正常；无横向溢出。
- 详情 Capabilities：刻度跳转后当前标记与焦点一致；继续滚动时章节 H2 与导航均停驻于 32px，上一章节标题随章节离开。
- 1024×900 深色、1280×900：无横向溢出，刻度轨道和正文保持在各自列内。
- Cf 游标随 40px 原生滚动从约 x=212.29 移至 x=220.92，投影同步落在实际坐标轴；切换减少动态效果后游标隐藏、动态投影清除，完整曲线保留。
- 1440×800：Work 原生文档确有滚动距离，大弧随滚动改变变换；宽高容纳全部页面时不人为增加滚动。
- 工具标题进入本地真实工作空间，读取项目库成功；返回原详情页，焦点恢复 Open Plimsoll。没有创建或修改项目。
- 重播图标可启动既有开场。键盘 Tab 可从标题进入 View Project；混合指针/焦点边界另外有回归测试。

音效频率、包络、静音、节流与资源释放已验证；未做听感验收。动画审美可在本地预览继续微调。本轮没有新增依赖、修改移动端设计、后端或全局字体文件。

## 主要文件

- `TitleEntry.tsx` / `titleEntry.css`：共享标题入口及次级操作。
- `ReadingRuler.tsx` / `readingRuler.css` / `readingScroll.ts`：刻度、章节定位及声音授权。
- `scrollStudies.ts` / `pageGeometry.tsx` / `pageGeometry.css`：图案方程与滚动绘制。
- `Portfolio.tsx`：生命周期与路由组合；`ProjectDetail.tsx`、`AboutContent.tsx`、`Contact.tsx`：章节元数据及标题。

预览：`http://127.0.0.1:5173/#/work`。本地 API/worker 继续运行以支持真实工具往返；发布工作未在本轮执行。
