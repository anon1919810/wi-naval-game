# 2026-10-09 计算核心独立审查修复

> **2026-10-10 发布后附记**：本页修复已随 `3a51f03` 提交、推送并部署。本次补验后台 62/62、零跳过，含此前缺少测试库的 PostgreSQL 两项专项；公网 8/8 通过。当前发布与核心能力见 [生产发布记录](core-release-2026-10-10.md)。下文保留 10 月 9 日本地修复验收时的事实。

本轮针对独立审查的 F01–F21 修复计算、数据来源和运行状态问题。未修改前端、字体、历史输入或 Taylor 图谱；未提交或部署。

最终全量回归：核心 **801/801** 通过（447.989 s）；后台 **60** 通过、**2** 跳过（29.86 s）。两项跳过是未配置独立可丢弃 PostgreSQL 测试库的鉴权/worker 专项，不作为 PostgreSQL 验收通过。新增 55 项核心回归及 10 项后台回归，原测试要求未放宽。

独立复验：进水/稳性 22 项、范围/阻力 32 项、遗留解析与前体控制 92 项、账本/来源 376 项、数值补充 25 项全部通过；运行状态/输入/CLI 为 62 场景、401 断言全部通过。最终测试前后 34 个修改或新增的 Python 文件哈希一致，原审查的 128 份证据哈希未变，`git diff --check` 通过。上述数字属于本地修复代码，公网未更新。

## 修复清单

| 编号 | 修复后的行为 | 永久回归 |
| --- | --- | --- |
| F01 | 进水的 gross 预算只限制步长，真正的净传输到达边界才报舱满或干舱 | `test_audit_flooding_stability` |
| F02 | GZ 采样恰落根附近时仍保留实际符号夹根；失败样点断开夹根，下进水之后不报完整稳性 AVS | 同上 |
| F03 | 弹药汇总全部唯一的实际绑定项，未知和已知零保持区别 | `test_audit_ledger_provenance` |
| F04 | 估算采用 true/false/null 三值合成，结构化来源与燃料绑定来源延续到局部 trace；明确无油保留声明，续航仅依赖消耗燃料 | 同上 |
| F05 | 非法来源类型拒绝；空来源草稿可保存，但不标为来源完整或区间 certified | 同上 |
| F06 | 显式非 keel 的遗留重量 datum 拒绝迁移，要求先明确换算坐标 | 同上 |
| F07 | 遗留水线解算使用当前横倾/纵倾后的顶点支撑，检查括区和体积残差 | `test_audit_legacy_geometry` |
| F08 | 水面横向惯性矩按实际占据的各区间积分，不把 U 形空隙当水面 | 同上 |
| F09 | 有 LCG、没有 LCB 时仍计算新增重量后的 LCG；不伪造 LCB | 同上 |
| F10 | 关闭连接不需要液面；打开的锁定重心部分液舱明确报模型不适用 | `test_audit_flooding_stability` |
| F11 | scenario、sea、tank、connection 的不支持压力字段明确拒绝 | 同上 |
| F12 | Taylor 完整性与项目 Re≥1e5 适用策略分离，逐行传到功率和反算结果并保留诊断 | `test_audit_range_policy` |
| F13 | 半入水角确实使用 at_frac，只在前体找目标半宽并插值斜率；钝艏无交点时不借用后体 | `test_audit_legacy_geometry`、`test_hull` |
| F14 | 过期回收与 worker 最终写入均为条件原子 UPDATE；旧 lease/fingerprint 不得覆盖新的终态，result/error/finished/lease 一起更新 | `test_audit_run_races` |
| F15 | 已知 KG 时 MCT 使用有符号 GM_L=KB+BM_L−KG；未知 KG 的 BM_L 代理明确标估算。Morrish KB 仍为估算 | `test_audit_legacy_geometry` |
| F16 | 非对象的 systems、systems.armour、systems.armour.fixed 产生准确路径诊断；HTTP 422 不写入新 revision | `test_audit_cli_runtime`、后台 `test_projects` |
| F17 | CLI 用法、非法 sweep 类型、序列化与写入错误遵守 JSON stderr/exit2；正常 partial 仍 JSON stdout/exit1，写入失败报告实际已保存路径 | `test_audit_cli_runtime` |
| F18 | 可选发动机排水量和 LWL 即使未参与计算也严格检查；Admiralty/Froude 输出有限 | `test_audit_range_policy` |
| F19 | 可选装药量始终要求有限非负，零装药有效；弹药计算不输出非法负数或无穷值 | 同上 |
| F20 | 单位、重量/力矩/区间/coverage、燃料/续航、压头与体积/质量流量均检查数值范围；可表示结果避免中间溢出，真正越界明确失败 | `test_audit_range_policy`、`test_audit_flooding_stability` |
| F21 | 最早甲板接触用端点最小干舷，均值仅作均值；B/2 恒宽近似不再冒称下进水或 GZ 有效性截止 | `test_audit_legacy_geometry`、`test_freeboard` |

## 结果身份

协调器版本为 `selected-loading-analysis-2`，稳性版本为 `loaded-projected-equilibrium-2`，连通进水版本为 `connected-quasi-static-flooding-3`，液压内核版本为 `vented-orifice-network-2`，阻力适配器版本为 `selected-plane-resistance-adapter-2`。请求身份包含版本；旧结果不会因输入相同而被当成本轮修复结果。物理公式方法名、图谱和不可变历史结果不重写。

## 仍然存在的模型边界

- Re≥1e5 是项目的保守主结果策略，不证明流态或实船精度，也没有新增层流阻力模型。
- 尺规/型线积分、显式 Euler 进水、锁定液体代理和近似干舷/MCT 的各自限制继续保留。
- 很小的残余液相可能无法解析出可信重心；长时进水仍会诚实报液相/平衡限制并保留最后接受状态，不强行算完或伪报舱满。
- 多文件 CLI 输出各自原子替换，不提供跨 JSON/CSV 文件的回滚事务。
- `certified` 仅表达所声明的区间和来源元数据是否齐全，不是船舶工程认证。

最终回归与独立复验的机器证据保存在本次任务的 `outputs/core-fixes-2026-10-09`，原审查反例和失败记录保留。
