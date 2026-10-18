# 动力、续航与性能阅读闭环交付（本地验收完成）

2026-10-19，本轮在既有工作树本地完成实现与集中验收。未暂存、提交、推送或部署；没有改动计算核心、后端、部署脚本、依赖或模型配置。起始 HEAD 仍为 `b24c73adbe26db47cad2c0fa83b394d136ce8e41`（产品基线 `b24c73a`，生产发布 `ae305b2` 已另行验收）。

Codex 已完成下述独立验收，当前为本地候选，未提交或部署。线上仍是上一批 `ae305b2`，详见[已发布记录](../formfield/release-native-ui-2026-10-19.md)。[机器可读验收](evidence/propulsion-performance-2026-10-19.json)与当前任务的完整回执共同界定本轮结论。

## 使用效果

- 普通动力章节在字段之前先给出读数：燃料 → 主机 → 传动 → 轴数的声明链、来源最大／巡航航速、最大／巡航马力、续航、煤比例、正常与最大载煤燃油，以及来源机械质量。航速跟随读者的单位选择，其余均为来源自身单位（hp、nmi、LT），按原样显示、绝不改称。
- 同一章节给出结果自己声明的功率锁定：`design.editing.power_locked / power_hp / locked_bunker_lt`。true、false、缺失三态严格区分；缺失的锁定值显示为未知，绝不显示为 0；缺失的锁定声明不写成“未锁定”，而写成“未声明锁定”。
- 两条全舰角色 machinery、fuel 以吨显示 `selected_mass_t`、`estimate_t`、策略与未绑定状态，不向设备或燃料类型分摊。来源机械质量（LT）与全舰台账质量（t）并排显示、彼此独立，从不合并。
- 性能章节按稳性、船体强度、适航性三组展示来源经验读数，并保留来源单位：经验得分为原值，来源经验推算的初稳性高为英尺、横摇周期为秒，两者均不换算。八个来源警告／评级标记 `tenderWarn、capsizeWarn、steady、unsteady、badSea、poorSea、goodSea、fineSea` 以 true／false／未知三态呈现；false 仅表示该一项，绝不构成总体通过；未知不是“否”。阈值仍归来源所有，浏览器不重新定义。
- 实时章节的读数按钮揭示并聚焦真实字段（`speed_max_kn`、`speed_cruise_kn`、`range_nm`、`shafts`、`coal_percentage`、`trim`）；性能页可直接定位 trim，并打开相关章节（船体、干舷、装甲、武备、重量）。这些控件只做定位，不设置任何设计值。
- 冻结报告在运行身份卡内复用同一读数，只读呈现、无编辑或跳转按钮，且不请求实时预览。草稿 pending／failed 完全隐藏旧数值与操作。

## 本轮实现

新增（均为前端、纯呈现或纯投影）：

- `web/frontend/src/components/propulsionPerformanceModel.ts`：纯函数 `readPropulsionPerformance(result: unknown)` 投影 `engine`、`performance`、`design.editing` 与台账角色 machinery／fuel；导出 `propulsionEnvelopeGate(envelope, result)` 作为父阶段包络闸门。不计算任何船舶数值、不读取实时宿主。
- `web/frontend/src/components/PropulsionPerformanceReadings.tsx`：导出 `PropulsionReadings` 与 `PerformanceReadings`。
- `web/frontend/src/i18n/propulsionPerformance.ts`：中英双语字典，复用既有枚举表与台账策略词。
- `web/frontend/src/styles/propulsionPerformance.css`：局部样式，窄屏单列。
- `web/frontend/src/__tests__/propulsion-performance.test.tsx`：22 项聚焦用例。

接入既有文件（仅在指定位置扩展）：

- `ShipDesignEditor.tsx`：动力／性能章节在字段之前挂载两个读数，复用其字段揭示令牌；性能读数额外接收章节跳转回调。
- `pages/Workbench.tsx`：仅把既有 `goChapter` 传给性能章节。
- `Sps3b3Readings.tsx` 与 `StageStatus.tsx`：原生报告把父阶段包络传给两个新读数并加以闸门；冻结报告不调用预览 API。
- `designFeedbackModel.ts`／`i18n/designFeedback.ts`：比较读数由 9 项增至 16 项（新增巡航航速、巡航马力、横向与纵向强度、适航性、来源经验高度、横摇周期），沿用同一提取与方向。比较的两个入口（草稿 `nativeDraft` 与冻结 `frozenRead`）共用同一状态判定：结果自身的 `status` 仅 `available`／`partial` 可被引用，`unavailable`、失败或缺失状态即使 schema／method 完好也扣留全部读数、台账角色与冻结配置表，并给出专门的“状态不可读”告警（`feedback.incompatible.status`／`feedback.frozen.status`），绝不误报为方法不符；`partial` 仍正读。
- `designConfigModel.ts`／`i18n/vesselOverview.ts`／`DesignFeedback.tsx`：冻结配置表新增轴数、航程、功率锁定声明与锁定目标，均来自各自冻结结果；新增 `canonical` 行以“来源单位 + 数值”原样呈现、绝不换算。
- 更新受影响的具体计数断言与同源文案（`design-feedback.test.ts` 的 16 键断言、若干“九项”措辞）。

## 独立验收（Codex）

- 集中相关前端簇 10 文件、140 项通过，包含工作台按需加载回归；生产构建通过。保留既有 Scene 分块体积提示。
- 只读审阅发现比较入口遗漏负载自身状态闸门，已修正为仅接受 available／partial；新增 3 项回归，独立复验受影响的两文件 33 项并重建通过，没有重跑完整簇。这是追加修复复验，不将重复用例相加。
- 自有 `127.0.0.1:8041` 隔离 SQLite 与真实 API／worker 完成 1 项目、3 修订、2 运行。基线修订 1 与新修订 3 对照，原运行和修订 1 文档保持一致。
- 在实际界面把机械角色设为声明质量 6000 t，航程改为 7500 nmi、trim 改为 50 并锁定功率。来源机械质量仍为 5722.131836 LT，台账来源估重为 5813.954364 t；三者独立呈现，人工值经保存重载及重算保留。
- 实际按钮定位并聚焦 range_nm 与 trim；性能相关章节按钮打开船体，草稿未丢失。受控预览延迟／503 时隐藏旧读数，原重试按钮恢复后展示新航程。
- 最终构建的中英冻结报告均无编辑控件或预览请求。16 项读数比较按“对照减当前”，航程差为 −500 nmi；轴数、锁定状态与锁定目标来自对应冻结结果。旧运行数据完整相同。
- 中文深色 390px 页面无横向溢出，动力、质量与性能三个视口已目视检查；英文桌面读数及表格已核对。
- 292 个核心、后端与部署源文件摘要保持一致。当前 HEAD 仍为 b24c73a，依赖与模型配置不变；隔离环境无活动计算。

完整证据位于本任务 `outputs/propulsion-performance-2026-10-19/`：`acceptance.json` 包含前端源摘要，另有测试／构建日志、API／浏览器回执和截图。原生打印对话框与打印分页未验收，未取得实船校准数据。

## 早先实现方检查（历史记录）

以下为本轮实现后的早期本地结果，随后又按上层 P2 复核做了两处小范围修复（补入来源机械质量 `engineWeight`；比较两个入口的状态闸门），并只重跑了受影响的两个文件。**这里的数字不是最终独立验收**；最终集中结果由上层补充。

命令均在 `web/frontend` 下运行：

1. 聚焦新用例：`npm test -- src/__tests__/propulsion-performance.test.tsx` → 22 项通过。
2. 集中相关前端簇一次：
   `npm test -- src/__tests__/propulsion-performance.test.tsx src/__tests__/armament-overview.test.ts src/__tests__/armament-overview-ui.test.tsx src/__tests__/native-report-readings.test.tsx src/__tests__/native-design-projection.test.tsx src/__tests__/ship-design.test.tsx src/__tests__/design-feedback.test.ts src/__tests__/design-feedback-ui.test.tsx src/__tests__/sps3b3.test.tsx`
   → 9 个文件、136 项通过。
3. 构建一次：`npm run build`（`tsc -b && vite build`）→ 通过（保留既有的大 chunk 体积告警，未在本轮扩展优化范围）。
4. P2 修复后仅重跑受影响的两个文件：`npm test -- src/__tests__/design-feedback.test.ts src/__tests__/design-feedback-ui.test.tsx` → 2 个文件、33 项通过。按上层指令未重跑完整 9 文件批次与构建。

未重跑未改动的 Python、后端或完整字段矩阵。

### 覆盖的边界（新用例）

- 缺失／异构 schema／异构 method／无 engine 与 performance；`unsupported` 不泄漏任何数值。
- 状态闸门：`available` 与 `partial` 可读且保留部分数据；`unavailable`、`failed`、`completed` 及缺失状态一律不可读、残留负载不呈现。
- 来源单位与“零／未知”：真实零是事实；缺失字段、数字字符串、非有限数一律未知。
- 选择器数组严格判定：缺失、长度不符或含非布尔项一律未知，绝不误报“无选择”；精确全 false 为显式未选。
- 锁定三态与缺失目标；来源机械质量（LT）与台账（t）分离。
- 三组性能读数与 ft／s 不换算；八个源标记三态。
- 不可变性（读取与包络闸门均不改写入参）。
- 冻结包络闸门：无包络放行；未请求／失败拒绝；completed／partial 放行；声明内核与负载 method 不一致拒绝。
- pending／failed 抑制、unsupported 命名、frozen 无控件、相关章节与 trim 回调。
- 中英字典键一致且均非空；中文断言。

## 未覆盖／受限（诚实边界）

- 原生打印对话框与打印分页未实查；上述浏览器验收不扩大为打印验收。
- 未接入“重算功率／航速”按钮的实时求解行为；本轮只读声明，不承诺界面实时求解，也不改写该按钮。
- 不做任何物理重算：不产生功率曲线、不重定义阈值、不给安全或精度结论；来源机械质量与全站台账质量不做换算或合并。
- 未新增或改动 SVG／PNG 下载功能。
- 未重复运行不变的后端／核心完整矩阵；真实隔离 API／worker／数据库流程已由 Codex 完成。

## 保护与边界

- 仅改动 `web/frontend`、本轮文档及状态索引；没有删除既有文件。
- 起始仅两份未跟踪的计划／规范文档为脏；其余改动均在本轮新增或指定接入点扩展，未删除既有文件。
- 无新依赖、无 provider／模型配置改动、无提交／推送／部署。
