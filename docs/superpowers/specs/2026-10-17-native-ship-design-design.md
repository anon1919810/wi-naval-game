# Plimsoll 原生舰船设计统一整合

用户已明确目标并授权推进：Plimsoll 自身全面覆盖本机 SPS 3b3 已有功能并现代化；先满足此最低标准，再添加增强项。上一轮兼容核及对照作为实现基础，不再以独立兼容模式可运行为产品完成条件。

## 用户可见的完成状态

- 一个工作台、一份舰船设计。普通章节直接编辑全部原设计能力，取消标准/SPS模式切换和两份可编辑设计数据。
- 船体、干舷、五炮组、五类辅助武器、装甲、动力、性能和注释均在主流程可达。修改一次，预览、保存、估重台账、平衡和报告一致更新。
- 新建初步设计无需CG或型线；估重、原经验性能和完整报告始终按已有输入可算。缺失位置不填0，物理分析保留真实缺项状态。
- 旧sship与现有兼容工程转入原生设计；旧物理工程可在普通工作台补充原生设计，不删除旧数据。JSON/CSV、原文件、富文本、复制/打印及图形继续可用。

## 一份权威声明

新增 project.ship_design，schema=plimsoll-ship-design-1，含parameters/editing/source/notes/condition_id/mass_bindings。复用已验收的222字段、单位和源事件语义；字段目录是内部计算注册表，不构成另一个产品。parameters仅保留一份可编辑事实。通过纯适配器临时转换为sps_compat声明调用旧核，结果从不反过来猜测用户声明。

原sps_3b3_design仅作为旧输入读取边界。显式升级后移除该活跃段，新ship_design接替；旧保存修订及原migration字节不改。两者同时出现时拒绝，不能猜优先级。

project.hull中的lwl_m/loa_m/beam_m/beam_bulges_m/draught_normal_m/draught_deep_m/block_coeff/waterplane_coeff为原生声明的SI投影视图，供现有核使用。原生普通表单只编辑权威声明，不再展示另一套重叠船体/军备参数。直接JSON修改出现投影冲突时结构化拒绝；普通命令返回重新投影后的完整工程。保留其他hull字段及来源，geometry绝不按尺寸自动改造。

现有系统的空间/位置/来源/绑定及物理载荷属于同一对象的补充资料；原生参数表取代重叠的旧编辑入口，明确的高级编辑仍保留。不能靠把两个编辑器并列、改名或隐藏模式按钮冒充数据整合。

## 一份重量台账及所有权

新增纯ship_design_mass模块，从当前完整计算结果产生有方法身份的质量建议（内部LT转换为t），不产生坐标。质量角色为structure/guns/mounts/gun_armour/ammunition/machinery/fuel/stores/auxiliary/belt_main/belt_ends/belt_upper/bulkhead/bulge/deck/conning及五类misc。stores为源loadWeight减已分开的bunker和magazine，不能再同时计入整项loadWeight；gun_armour不能重复计入固定装甲总重。残差船体保留原定义，不把它冒充物理结构强度证明。

每角色有mass_bindings[role]={item_ids:[...],mode:'estimated'|'declared'}。新建空台账自动建立一个带owner标记的设计组，估算质量随设计刷新；未知位置保持null。已有项目按明确的concept_design.balance.roles匹配角色，已有人工质量默认declared且不改，建议质量单列。没有明确角色的旧项目标needs_binding并在统一重量页给出绑定选择，绑定完成前不加入可能重复的自动重量；基础参数计算与报告仍可用，台账平衡诚实标待接入。

一个item只能归属一个角色；不同角色不能重用同一ID。estimated绑定只允许一个受管目标；declared允许多个项目累加。切到estimated是重量页明确的采纳动作，保留位置/来源历史并记录替换前质量。不得删除旧项目或覆盖人工质量。旧计算运行不随新绑定重算。

原生估重组只服务ship_design.condition_id，必须为显式非派生工况。重量项以design_mass={owner:'ship_design',condition_id,mass_t,source}记录受管替换质量，加载解析器在既有继承/override之后，仅当工况ID精确匹配才采用。新自动项base.mass_t=0表示明确不纳入其他工况，已有目标的base、来源、位置、原override和派生definition原样保留；不能给派生工况追加schema禁止的override。未知或负的源残差保留null及诊断，不用0补缺失质量或CG。

旧concept_design及systems重叠声明保留为高级资料，但原生工程不得再由这些声明向受管目标生成另一套可采纳估重建议。固定角色迁移表：rotating_armour/gun_mount_armour合为gun_armour，armour_deck→deck，armour_bulge→bulge；聚合includes所有权混合/重叠必须needs_binding，不能只改名就自动增加明细项。基础设计报告显式携带basis_condition_id；选中另一工况时物理分析使用所选工况，而设计平衡仍使用自己的设计工况并明确标注。

预览、保存和分析入口共用同一纯投影一致性契约：estimated受管质量、SI维度或所有权被直接JSON/旧采纳路径修改时拒绝，先明确切换declared；set_declared_mass {item_id,value}只改设计工况的明确人工override及来源，其他工况不变。切换estimated→declared保留当时有效质量，不能回退新项base的排除0。

统一balance同时报告selected_mass_t/estimated_mass_t/target_displacement_t/difference_t和binding状态。新建的全估重设计应与原正常排水量在容差内闭合；已有人工质量与估算不同属于可审查的设计差额，不能被隐藏或强行补差。后续物理分析读取同一份台账。

## 计算与报告

新增analysis阶段ship_design，基础依赖[]；内部复用已核对的纯核，保存原生结果、源适配声明、统一台账摘要与不可变报告。原生工程默认只请求该基础设计阶段；普通工作台内可另行请求现有物理阶段，不能因此使基础设计失败。

报告统一在现有Run/Report流程，原功能章节、诊断、四级排水量、文字、文件导出继续保留，另标已选台账与估算差异。ship_design为产品身份；sps_compat仅为旧运行读取与内部对照。JSON/CSV比较接入原生设计关键读数和实际方法/单位，不把经验评分写成物理GM等别的量。

## Web契约

/api/design/catalog、/api/design/preview、/api/design/initialize、/api/design/import-preview、/api/design/from-migration；鉴权/CSRF/归属沿用既有机制。预览是无写入操作，接受完整project、可选command、可选最新design，返回{project,design,preview,status,diagnostics}。并发串行队列保留草稿，丢弃旧工程/旧代次回复，修改确认完成前禁用保存运行。所有接口沿用1MiB请求和原文件字节界限。

网页新建空设计以template='ship_design'请求服务初始化原生设计（实际产品默认，不是用户船舶事实）；旧API的template=null保留空白语义，既有物理模板不自动重写。读取旧兼容工程时在前端形成待保存升级草稿，保存后才有新身份，旧运行仍读其原修订。新旧项目可共存但没有两个用户模式开关。

## 边界与验收

- 暂不加曲面装甲、额外损伤、更多船型经验法等增强项；保留原有已实现高级能力。
- 沿用现有Python/FastAPI/React，不引依赖；当前已隔离工作树，153个起始改动已完整ZIP与摘要保护。无提交/推送/部署。
- 少量有判别力测试：新空工程完整闭环；源导入等值；一次船宽/炮组/装甲修改贯通共享投影、台账、报告；人工质量保护与绑定冲突；工况隔离；延迟回复与旧报告保护。
- 阶段集中验收，最后实际主界面新建→编辑不同章节→台账→保存→运行→报告/下载→原版重开→重载。不得以删除模式按钮或测试数量替代通过。

实现者决定：本轮保留内部源字段和尺度以复用已验收核；规范单位投影用于现有物理接口。后续可以迁移存储格式，但本轮不把该无用户收益的改写作为前置条件。
