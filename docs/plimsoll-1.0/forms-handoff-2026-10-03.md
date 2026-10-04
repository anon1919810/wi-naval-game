# Plimsoll 六页输入表单交接

后续高级输入、破损操作和显示单位已于 2026-10-04 补齐，见[最新交接](advanced-workflow-handoff-2026-10-04.md)。下文是本轮六页表单完成时的历史状态。

2026-10-03，本轮完成 [六页表单计划](long-task-sps-pages.md) 的 Guns、Weapons、Armour、Engines、Performance、Hull 输入与结果展示范围。已有 Weapons 改动先提交为 `f0556e0`。新实现保留既有 Freeboard 表单、主尺度六项输入、Python/API 入口与 15 阶段计算协调器；没有新增数值求解器。

仓库为 `C:\Users\杨睿\Documents\Codex\2026-09-17\shi\work\plimsoll-1.0`，分支 `feature/plimsoll-1.0`。本轮仅保存本地提交；桌面主资产仓库、Unity、服务器不在此次修改范围。

| 本地提交 | 内容 |
|---|---|
| `f0556e0` | 先整理提交已有 Weapons 表单改动。 |
| `161bea2` | 明确的派生载荷规则、可选设计声明、炮弹报告事实与独立主带投影，以及核心测试和契约文档。 |
| `e65e361` | 六页前端集成、当前结果读取、字段与估算展示、输入保存及异步结果保护测试。 |

## 用户现在能做什么

进入舰船工作台后，可直接编辑六页的已声明字段、来源和估算状态，保存不可变修订，选择工况并计算。结果区读取后端结果，不在前端重算聚合。最近运行列表不含结果体时，工作台只补取一个匹配的完成/部分完成运行；修改草稿、切换工况或修订后，旧结果立即隐藏。请求选项随运行保存，尚未提交的请求草稿不跨重开保存。

空白项目可建立炮组、鱼雷分区、杂项分区及装甲行，并选择现有账本条目。五个杂项分区的声明质量只是报告信息，系统质量仍来自账本。清空数值保留未知；炮数因既有契约不接受 null，清空时省略对应键。0 始终表示明确的已知零值。

## 字段与结果映射

| 页 | 主要输入位置 | 结果位置与边界 |
|---|---|---|
| W1 Guns | `systems.weapons.<battery>.installed_guns / broadside_guns / rounds_per_gun`；已有弹药模型输入及来源；无模型时的 `facts.projectile_mass_kg`；`weight_item_ids` | `systems.data.page_rows["weapons.<battery>"].guns`。单舷/每炮弹重与全舰账本弹药分开；报告事实不生成装药或账本质量。 |
| W2 Weapons | `systems.weapons.torpedo / misc_weight` 的类型化 `page_rows`、来源、三态估算、行与分区账本绑定 | 同名 `systems.data.page_rows`。支持重复主/副鱼雷、水雷、深弹及五个杂项位置分区。行绑定与未分配绑定取并集，末行删除省略 `page_rows`。 |
| W3 Armour | `systems.armour.fixed.page_rows` 的厚度、纵向端点、高度、类型、分组、来源、估算与绑定；`deck_coverage`、`minimum_main_belt`；炮组 `rotating_armour_component` | 装甲分组小计与三项研究。覆盖率基于有来源的平面面积；主带独立取声明的舱段范围与余量；旋转装甲拆分不增加总质量。 |
| W4 Engines | `systems.propulsion.facts`、机械绑定、`fuel_bindings`、`variable_load_groups`；`endurance_scenarios` | `propulsion.data.engine_page / values / effective_case` 与 `endurance.data.values`。机械质量、燃料库存、可变载荷、煤比例及续航，均取所选账本与后端计算。续航保留估算标记与来源。 |
| W5 Performance | `loading_conditions[].definition` 与已有覆盖项；`hull.roll_gyration_coeff / sources`；本次请求的阻力场景、速度、QPC、给定功率、目标纵倾、续航场景 | 所选总质量、GM、横摇、目标纵倾力矩、功率采样及给定功率求速度。`estimated_nonprimary` 数值可展示但明确标成非主工况工程估算；失败/未知不显示伪数值。 |
| W6 Hull | 保留主尺度六框；`metadata`；`hull.draught_deep_m`；`hull.design_facts`；`display_preferences` | `l0.data.declared_hull / hull_ratios` 与 `hydrostatics.data` 的当前水线面积、湿面积、体积、排水量、长宽比。参考排水量/满载设计系数不会替代所选质量或实际几何。 |

表中阶段前缀均为 `stages.`。核心契约详见 [项目扩展](project-extensions.md)、[载荷契约](loading-contract.md)、[页面行投影](page-rows-contract.md)。

## 对七页清单的侦察结论

`evidence/seven-page-binding-proposal.json` 保留的是此前计算绑定审计快照，不是此次前端完成度统计。191 条记录中，六页包含 160 条：Guns 10、Weapons 40、Armour 38、Engines 28、Performance 22、Hull 22；另有 Freeboard 24、公共控件 7。记录同时包含结果、控件、排除项，不能把“160 条”称作新增 160 项计算。

| 页 | 本轮所接既有契约及缺口处理 |
|---|---|
| Guns | 复用已确认的炮数、弹药模型和账本投影；添加可选报告事实的入口与投影，不猜未被观测的炮组编辑器字段。 |
| Weapons | 核心已有重复类型化行；本轮补齐空白建项、增删、五区声明、来源与估算状态，以及行/分区绑定保留。Queen Mary 五区未知不倒填。 |
| Armour | 复用已声明的厚度/范围和三项研究；修正范围校验、末行删除及主带研究不应依赖存在装甲行的集成缺口。 |
| Engines | 机械、锅炉、能源、传动、煤油及可变载荷均已有契约；表单直接接入。动力性能采样通过 Performance 选择既有阻力研究，不重复实现功率公式。 |
| Performance | 之前 Standard/Light 仅要求命名工况，本轮补齐明确的基准与扣除规则。稳定性、耐波性和破损耐受评分仍为已批准排除项。 |
| Hull | 主尺度已可编辑；复用身份、最大吃水、单位偏好，新增独立的满载设计方形系数和正常/满载参考排水量声明。自然速度仍未实现。 |

## 必须保留的限制

- Standard/Light 是用户定义的扣除研究，要求另一个非派生基准、具体条目、来源和明确估算状态；空扣除列表表示不扣除。禁止派生链与同时声明额外覆盖项。不会擅自扣除煤、弹药、人员或水。
- 主带长度是独立工程估算，不是 SPS 原公式。缺完整且有来源的关键舱段范围返回 unavailable；前端只选择已有舱室，舱室几何仍由项目数据/API 编辑。
- 所选模型适用范围之外的结果保留后端状态，不伪装有效的主工况功率或航速。目标纵倾只报告所需力矩，不表示载荷已移动或纵倾已达到。
- 单位偏好目前只记录选择。实际输入、计算和报告保持项目规范单位（m、t、kW、kn、deg），尚未实现显示换算。
- 阻力场景定义、详细弹药质量模型、舱室/破损及其他高级字段仍由“项目数据”JSON/API 编辑。这轮六页表单不承诺任意项目完全无需 JSON。
- Queen Mary 缺史实输入保持未知。不实现 SPS 专有评分、自然速度、未观测炮组字段、Cost & Strength、公网部署或真实邮件验收。

## 验证证据

按用户要求集中测试；核心冻结后只运行一次全量。OpenCode 实现经过两轮审查后，剩余前端修正及文档由 Codex 接回，并独立执行下列检查。

| 检查 | 实际结果 |
|---|---|
| 核心全量 `python -B -m unittest discover -s tools/plimsoll/tests -q` | 735 项通过，416.817 秒。随后没有核心代码改动。 |
| 后端 `pytest web/backend/tests -q` | 33 项通过、2 项 PostgreSQL 专项跳过，17.07 秒；1 条第三方 Starlette/TestClient 弃用警告。此次不重新声明 PostgreSQL 验收。 |
| 前端全套 `npm.cmd test -- --run` | 7 个文件、51 项通过，11.12 秒。 |
| 最后审查补测 `npm.cmd test -- --run src/__tests__/remaining-forms.test.tsx` | 17 项通过，7.08 秒；包含新增的续航估算标记测试。当前前端测试共 52 项，但最终未再重复全套。 |
| 最终生产构建 `npm.cmd run build` | TypeScript 检查与 Vite 构建通过，42 个模块；未添加依赖或修改锁文件。 |
| 实际浏览器与独立临时 SQLite | 测试邮箱登录 → 解析方箱 → 新炮组与报告弹丸事实 → 保存/后台运行 → 重开后补取结果 → 鱼雷行绑定与未分配分区绑定保存。修订 3 的数据库记录核对并集与弹丸来源/估算均保留；随后装甲增删末行并成功保存，按钮恢复为已保存状态。 |
| 差异审查 | 修正空行保存、绑定丢失、结果错用工况/修订、主带投影依赖及估算误标等问题；不新增质量，不在前端复算。 |

完整测试输出保存在本地忽略目录 `.superpowers/sdd/long-task-sps-pages/` 的 `core-final.log`、`backend-final.log`、`frontend-final.log`、`frontend-followup.log`、`build-final.log`。临时浏览器数据库不是正式用户数据库或迁移验收证据，不提交验证码、凭据或数据库。

## 重开与后续

按 [本地运行文档](web-local-operations.md) 启动 API、worker 与前端，进入原有项目即可看到六页；旧项目无新增声明时保持缺失/未知。不需要重生成 Blender 或打开 Unity。正式数据库仍使用版本化迁移；临时 SQLite 浏览器验收不替代正式部署流程。

下一阶段可单独选择显示单位换算、阻力场景表单、详细重量模型编辑或服务器部署。它们不属于此次六页输入范围，不应通过擅填历史数据来提高“完成率”。
