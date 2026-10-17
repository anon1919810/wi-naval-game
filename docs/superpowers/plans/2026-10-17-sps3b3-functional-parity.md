# SpringSharp3b3 Functional Parity Implementation Plan

> 用户已授权自行设计并执行，无需逐项再确认。Codex规划、审查与独立验收；OpenCode实现有界单元。使用opencode-delegate工作流；必要内联修复遵循executing-plans。不得提交、推送或部署。

**Goal:** 补齐本机3b3的输入、计算联动、文件与报告流程，先达到原版功能水平。

**Architecture:** 新增独立SPS兼容声明和纯计算依赖图，复用已恢复公式；隔离当前显式台账和物理计算。分别实现纯核、文件/报告、UI/analysis适配。

**Tech Stack:** Python、FastAPI、React/TypeScript；无新运行依赖。

**Spec:** ../specs/2026-10-17-sps3b3-functional-parity-design.md

## Global Constraints

- 保留112起始文件、原191清单、旧工程与原程序集；不复制恢复C#进repo，不改旧物理方法含义。
- 本轮不做新曲面/逐板CG/现代伤害仿真。
- 显式免费模型opencode/deepseek-v4.1-flash-free；不可自动付费fallback。
- 每单元一次相关批次，失败定向复验；共享UI末尾集中验收，不重复旧大矩阵。
- 同输入完整原程序集结果是等价证据；worker报告不是验收。

## Review Focus

1. 普通beam与beamBulges、Favg/Fdistributed/Fcap不混用；正常/深载不同量不相互覆盖。
2. H0/H1与源稳性额外borne项、内部支撑舱壁加回不被当前台账算法替换。
3. 0/未知/未选择和源NaN局部置0分开；警告不能隐式改值或导致整页丢已知值。
4. 25重复项、33padding、独立页单位、lb弹重和long-ton杂重保持源语义；旧格式不同字段表。
5. 新兼容草稿/保存运行/旧报告身份分离；尺度/锁定/批量命令及快速编辑不得旧响应反写。

## Task 0：当前基线与原程序完整链

- [x] 保存HEAD和112文件摘要及ZIP。
- [x] 三领域只读审计，区分已完成增量和真正缺口。
- [x] 原构造→隐藏Load→原openFileCalc→原报告方法受控执行成功。
- [x] 生成新当前功能/报告字段清单，逐项登记原路径与当前实现/证据。

## Task 1：后坐力、浮力承受量与命中数纯核

**Files:** 新增tools/plimsoll/sps_performance.py及tests/test_sps_performance.py。

**Interfaces:** evaluate(inputs,*,path='$')->{method_version,status,values,diagnostics,provenance}；精确输入输出见聊天work/plimsoll-sps-parity/performance-unit-brief.md。

- [x] 有判别力中心用例red→实现→定向green。
- [x] Codex用原完整控件链中的实际输入/输出比较四个读数。
- [x] 仅运行新文件：& './web/backend/.venv/Scripts/python.exe' -B -m pytest tools/plimsoll/tests/test_sps_performance.py -q

## Task 2：兼容声明与船体/干舷状态

**Files:** 新增tools/plimsoll/sps_hull.py、sps_compat.py声明部分、tests/test_sps_hull.py。

**Interfaces:** sps_hull.evaluate(parameters,*,editing=None,submerged_casemate=False) 输出原hull/freeboard命名的数值，及规范化parameters/editing、诊断；commands在sps_compat.apply_edit路由。

- [x] 独立凸舱宽、LWL/LOA与Cb/排水量驱动、源四段及三种干舷。
- [x] 单位变更、深度锁定快照、干舷预设、下游上下文单一来源。
- [x] 新增文件相关批次与原完整船体输出对照；不重写自然航速旧方法。

## Task 3：源部件、混合动力与重量/性能依赖

**Files:** 新增tools/plimsoll/sps_components.py、sps_engine.py；完成sps_compat.py；新增对应中心工作流测试。

**Interfaces:** compute(design)返回带方法/状态/诊断的hull/freeboard/guns/auxiliary/armour/engine/performance章节；parameters使用sship_fields注册名称和值，各页源单位。复用Task1/2及旧核。

- [x] 五炮组的总重/布局/炮装甲，七类固定装甲，五辅武器及空间；全0空组明确，不以缺值冒充0。
- [x] 多选机种/燃料/传动、源煤比例、功率锁与反算航速/航程。
- [x] 正常bunker、loadWeight、H0/H1、四级排水量、深载吃水与Cb。
- [x] roomFloat/roomHull/roomDeck、自动concentration/superFactorLong、源结构与稳性、经验GM/周期、Task1末端读数与造价。
- [x] 以当前原完整工程取有效输入逐项对照；按差异定位后只补相关中心用例。

## Task 4：源告警、军备描述与完整报告

**Files:** 新增tools/plimsoll/sps_gun_review.py、sps_report.py和对应测试。

**Interfaces:** review返回稳定code/source/condition/message；报告章节模型统一供web/TXT/RTF/SSR，读取同一保存兼容结果。

- [x] 原32枪炮跨字段规则、整船失败、动力/年代及空间/强度/耐波评价。
- [x] 自动军备描述、源条件文字、全部报告章节与追加注释。
- [x] TXT复制/RTF及SSR可互通；RTF转义Unicode/反斜线/大括号，不把文本伪装成RTF。
- [x] 原报告字段清单逐项核对，已有crew/cost等直接映射，不重做公式。

## Task 5：文件、analysis/API/CLI及兼容UI

**Files:** 新增sps_file_io.py、兼容editor/results/report组件；修改project_extensions/project_io/analysis/request/CLI、backend专用路由与前端API/types/Workbench/Report/i18n。

**Interfaces:** 可选sps_3b3_design；analysis stage sps_compat；纯草稿preview/command；保存运行沿用既有事务。无自动质量采纳至物理台账。

- [x] 完整3.0 serializer、SPS旧2.0有界读取（1.x按原版拒绝）及原归档保护。
- [x] 原280位置/权威后写项/页单位/lb与long-ton、notes，独占文件输出与新下载响应。
- [x] 七页普通编辑、输入主权/尺度/深度与功率锁/批量弹重/默认尺寸命令。
- [x] 快速编辑丢旧响应，预览和保存运行分开，兼容默认运行不要求原版无CG/型线数据。
- [x] CLI/JSON/CSV与文本/RTF/SSR导出；网页打印和复制。

## Task 6：阶段统一验收与收口

- [x] 少量判别力完整工程同输入原程序集对照，覆盖bulges/freeboard/mixed guns/mixed engine/locks/loading/legacy。
- [x] 实际界面保存→运行→导出→原版打开→重开，另做原程序集独立对照；字段、数值、告警、报告、注释及归档一致。
- [x] 相关阶段批次、最终共享UI构建、当前源码quick与源码/基线保护核对。
- [x] 新功能清单无差异/未验证才签署完全对齐；否则继续补足且如实保留状态，不先报完成。
- [x] 交付本地源码、可打开工程、对照证据、报告及可恢复快照；临时服务清理。

验收签署见 docs/plimsoll-1.0/sps3b3-parity-2026-10-17.md 和 evidence/sps3b3-acceptance-2026-10-17.json。免费OpenCode持续429后由Codex接手；该接管不改变原范围与独立验收标准。未提交或部署。
