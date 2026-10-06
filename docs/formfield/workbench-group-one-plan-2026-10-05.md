# 编辑页工作头与输入层级实施计划 · 2026-10-05

依据：`next-workspace-design-2026-10-05.md` 第一组。用户已指定执行，Codex 规划、审查和验收；OpenCode 实现。工作目录保持当前 checkout，以保留并行字体改动。

目标：在桌面编辑页一眼辨认章节、工况、保存修订与草稿状态，区分输入和保存结果，让字段来源可达且不遮挡编辑。

## 约束

- 标题 Space Grotesk，正文 Inter，中文系统回退；浅深色；不做移动端、部署、后端或计算核心修改。
- 不编辑或提交已有字体文件、index.html、portfolio.css、tokens.css 及字体文档。
- 保留公共页面返回目的地、转场锚点和匿名身份；不改变运行、保存、409 草稿复制/重载与 JSON 应用契约。
- 当前结果继续使用 currentRun 身份守卫；未知和零区分，不计算新指标。
- 显示偏好既有持久化编辑保持兼容；Trace 展开/选择属于界面状态，不改变项目。
- 按功能簇测试；不每一步跑回归。不提交、不推送。

## 实施单元

- [x] 工作头：Portfolio.tsx / App.tsx 合并外层 Formfield 返回条和应用页眉，保留真实链接及主题。Workbench.tsx 将工况、修订、保存状态、Save / Run 集中于操作条；错误、请求错误和冲突紧邻操作条；项目文档下载为次级动作。
- [x] 章节与概览：ProjectNav.tsx 增加静态编号，保留中文可访问名称；非概览主标题采用英文章节、舰名为上下文。Overview 移除通用船图，明确 Input、Result / Revision、工况与历史记录。保存结果仅取现有 stage 字段，保留阶段状态、缺项和诊断。
- [x] 输入与来源：新增聚焦来源上下文/组件，只消费显式 value/source/estimate 或 hull.sources、账本来源。FactInput、主尺度、重量及甲板等真实输入接入；普通字段没有来源时明确未知，通用说明不可冒充来源。未选字段 Trace 只显示引导；选择随草稿变化保持新鲜、章节切换清空。宽桌面约 200px / 自适应 / 240px；1024px 默认收起且通过明确按钮在文档流中展开，不遮字段。章节一级组用编号细线，减少嵌套外框；长说明可展开，必要方法边界/错误直显。可选请求排在输入后、结果前。
- [x] 行为验证：新增工作头、章节标题、来源三态、实时更新、Trace 非修改状态、无结果及 dirty/工况/修订结果失效测试。更新确因标题变化失效的查询，不削弱断言。

## 验收命令与人工检查

在 web/frontend：

```powershell
npm.cmd run test -- src/__tests__/workbench.test.tsx src/__tests__/remaining-forms.test.tsx src/__tests__/advanced-inputs.test.tsx src/__tests__/deck-form.test.tsx src/__tests__/gun-form.test.tsx src/__tests__/weapons-form.test.tsx src/__tests__/display-units.test.tsx src/__tests__/anonymous-workspace.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/workbench-hierarchy.test.tsx
npm.cmd run build
```

在仓库：`git diff --check`。Codex 独立运行命令并审查 changed_files；对比保护文件 SHA256。真实浏览器检查 1440×960 / 1024×900 浅深色、键盘字段与来源、长内容、重量/甲板局部滚动、返回；修订冲突与不匹配结果用确定性组件测试验证，必要时浏览器用隔离预览数据。

完成后记录实际交付与验证，第二/三组继续保留为计划。不以组件测试冒充真实计算、PDF 或部署验收。

实际完成于 2026-10-06；验证与兼容选择见 [第一组交接](workbench-group-one-2026-10-06.md)。
