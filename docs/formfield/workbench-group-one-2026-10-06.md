# 编辑页工作头与输入层级 · 2026-10-06

第一组已本地实现并验收，未提交、推送或部署。基于 HEAD `c68a289`（上轮界面 `6ce11d9`）；保留原有并行字体和全局样式改动。后续第二组也已完成，见 [运行与报告交接](run-report-2026-10-06.md)；本文件保留第一组的验收范围。

## 实际交付

- App 页眉统一真实总站返回、品牌、主题与身份；加载/身份连接失败仍可返回。保留总站转场和匿名工作区契约。
- Workbench 操作条统一工况、已保存修订、草稿状态、保存/运行；错误、请求失败和 409 冲突直显，复制草稿/重载保留。JSON 下载在更多操作中。
- 概览保留舰名主标题；其余章节用英文主标题和较小舰名上下文。静态索引编号保留中文可访问名称。
- 概览明确输入、当前工况/修订、严格匹配的不可变运行结果和历史记录，无通用侧视 SVG。脏草稿、修订/工况/项目不匹配均失去“当前结果”身份。
- 结果读取实际保存字段：总质量 `loading.values.total_mass_t`、龙骨基准水线高度 `equilibrium.waterline_above_keel_m`、横倾角 `equilibrium.heel_deg`、GM `hydrostatics.values.gm_t_m`。未给出、未请求、资料不足和模型越界不补零、不显示残留数字；不在浏览器推算吃水。保存诊断根列表与阶段列表去重。
- 一级组采用静态编号与细线，减少 form-card/fieldset 嵌套外框。单位长说明可以展开；输入边界、错误、诊断保持直显。性能/破损输入排在可选请求和结果前。
- Trace 接入 FactInput、主尺度、重量账本、甲板干舷/参考长度等字段；只读取自身 value/source/estimate，未知估算状态与 false 区分。结构化来源序列化供查看；甲板未编辑的原始来源对象保留其结构。
- 选择由已挂载控件身份管理，重复名称/路径不会串字段；草稿编辑实时刷新，删除字段/切换章节清除。面板按钮不会清空选择，普通无关联控件聚焦会清除旧信息。
- 宽桌面索引 200px、来源 240px；收起后顶部保留 96px 安静入口。1024 桌面默认收起，来源在中栏文档流展开；从长表单字段点击来源会滚动到面板，保持控件焦点，无遮罩。

## 验证证据

Codex 独立执行集中簇测试：workbench、remaining-forms、advanced-inputs、deck-form、gun-form、weapons-form、display-units、anonymous-workspace、portfolio-transitions、portfolio-content、portfolio、workbench-hierarchy，共 12 文件，212/212 通过。

末轮数据说明和破损顺序整理后补跑受影响 5 文件，93/93 通过；随后增加重量位置单位、破损输入/请求/结果顺序断言，workbench-hierarchy 30/30 通过。最终 `npm.cmd run build`（TypeScript 与 Vite）通过，`git diff --check` 通过。未重复全量前端回归。

只读复核没有剩余 P1/P2 问题。OpenCode 完成主体，Codex 按两轮审查未通过的委派规则接回修正。OpenCode 运行已停止。

实际隔离预览：1440×960 Hull/Overview 浅深色，1024×900 Hull/Weights/Deck/Damage；来源收起入口保持顶部，从长表单底部展开可见；键盘 Tab 可进入来源按钮，编辑后修订 1 仍可见且运行禁用，Trace 值及时更新；两种宽度没有页面横向溢出，重量/甲板使用局部 overflow 容器；总站返回落到真实 `#/work`。字体实际计算样式为 Space Grotesk / Inter。预览中未保存临时输入，重载恢复；没有发起新计算。浏览器宽度覆盖已恢复。

409 冲突、项目/修订/工况结果不匹配由组件测试验证，未在真实后端制造冲突或伪造保存运行。打印、PDF、计算数值正确性和公网版本不属于此次验收。

- [1440 浅色 Hull](assets/workbench-group-one-2026-10-06/workbench-hull-light-1440.png)
- [1440 深色 Hull](assets/workbench-group-one-2026-10-06/workbench-hull-dark-1440.png)
- [1440 概览](assets/workbench-group-one-2026-10-06/workbench-overview-light-1440.png)
- [1024 长表单来源](assets/workbench-group-one-2026-10-06/workbench-trace-1024.png)
- [1024 深色破损](assets/workbench-group-one-2026-10-06/workbench-damage-dark-1024.png)

## 兼容与后续

显示偏好仍按既有 display_preferences 项目字段编辑、保存；选择单位会产生草稿修改，和设计提案中的纯阅读状态设想不同。此次优先保留现有持久化契约与测试；Trace 选择/展开属于纯视图状态，不触发保存。

对保护文件逐一 SHA256 比对均一致：字体、许可/README、字体文档及截图、index.html、portfolio.css、tokens.css。工作区保留这些并行未提交文件，不重置、不暂存。

后续第二组“运行与报告阅读”已完成，第三组动效仍未实施。发布前仍需整合字体会话成果、检查干净检出并按既有部署流程另做公网验收。

> **发布后附记 · 2026-10-06**：本组改动已连同第二组与 Space Grotesk / Inter 字体随提交 `7131a78` 发布上线（`plimsoll-web-20261006T032422Z-7131a78`）。上文第一、二、三节的验收范围与证据为当时记录，未因发布而改写；上线与公网验收事实见 [2026-10-06 生产发布交接](release-2026-10-06.md)。第三组功能转场仍未实施。
