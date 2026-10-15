# Plimsoll 可信计算第二轮 · 本地验收

在 `2984cd3` 基础上新增显式离线 `verify`。最终冻结源码的 **38/38** 验证断言、**1134 项 + 594 子测试** 核心回归及既有 **98/98** 收敛研究通过。这里记录解析一致、数值误差和软件契约；外部实测仍为 pending。工作仅在本地，未暂存、提交、推送或部署。

## 新入口与证据

```powershell
$env:PYTHONPATH=(Resolve-Path -LiteralPath './tools').Path
$env:PYTHONIOENCODING='utf-8'
& web/backend/.venv/Scripts/python.exe -B -m plimsoll readme
& web/backend/.venv/Scripts/python.exe -B -m plimsoll verify --suite quick --output-dir 'C:\PlimsollVerify\quick'
& web/backend/.venv/Scripts/python.exe -B -m plimsoll verify --suite all --output-dir 'C:\PlimsollVerify\all'
```

`quick` 15、`extended` 26、去重 `all` 38。参数、退出码、恢复规则见[CLI 契约](cli.md)；随包指南为 `python -m plimsoll readme`。`help/readme` 不计算、不写文件。verify 的 0 只表示完整、一致源码和全部声明断言通过；计算/工作进程/期限/执行后发布失败为 1，使用或执行前输出拒绝为 2。

输出 `core-verification.json/.csv/.md`，JSON 为权威，三份须具有相同 run_id/generation；partial、缺失或混合代次不能读作通过。实际全矩阵 run_id **`b54d6f38-1f8b-4f50-84d8-a559904c6968`**、generation **39**、耗时 **608.234s**。源码身份包含 47 个实际包 Python/README 文件、加载来源与方法身份；测量的是磁盘源码，不作任意内存函数的密码学证明。

[仓库验收快照](evidence/core-verification-2026-10-10.json)保存源码、案例、误差、性能、复制清单、资料准备度及原始文件路径/SHA。[完整原始报告](<C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/core-verification-next-round-2026-10-10/final-matrix-v2/core-verification.json>) · [证据索引](<C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/core-verification-next-round-2026-10-10/evidence-index.json>) · [逐项完成账本](<C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/core-verification-next-round-2026-10-10/goal-acceptance-ledger.json>)。

## 数值结果与适用范围

尺度 0.5/1/2、干载/液载、非零倾斜镜像和 z 基准均实际调用公开核。绝对几何/CB 与龙骨相对 KG/舱底/孔口分别转换。同一有限网格的变换规律保持严格精度；连续积分误差单列，不把粗网格的离散误差说成坐标变换缺陷。

九组椭球网格为站数 41/81/161 × 每剖面顶点 32/64/128，三条对角线实际求自由浮态。最细网格直接体积相对误差 **0.000547345385**，直接 CB 最大轴误差 **0.00037193296m**；自由浮态吃水误差 **0.00134846005m**、斜率最大误差 **5.46162808e-07**，求解后 CB 最大轴误差 **0.00116506934m**。全部声明的最细精度及各级状态/残差闸门通过。固定另一轴的误差与观测阶保留在快照，不强行要求二阶。

单舱与非对称双舱分别请求 60/300s、dt=0.5/0.25/0.125s，共 12 次实际时间推进。逐接受态核对容量、有限量、平衡残差、最终态与时间，以及按声明连接方向重算有符号体积/质量账本。最细步长最大轨迹体积误差分别为 **0.006117878m³** 和 **0.004359596m³**，均在预声明的独立固定转移量尺度预算内；步长减半的观测阶约 **1.002–1.018**。粗步长误差和终止时间差保留为诊断，未扩宽容差。

300s 请求的最细单舱在 **62.2714844s / 502 步**、双舱在 **13.9628906s / 116 步**按水力平衡容差完成；这不是推进满 300s。单舱 60s 请求确实运行至 60s，双舱 60/300s 均早于请求终点达到平衡。双向初始水头、接收舱容量边界、3s 取消和反转保护各有实跑。预期 `model_limit`、`canceled` 控制的断言通过仍保留其原始状态。

参考层不用生产核构造答案：单舱分段解、双舱自由姿态/液柱矩及水头 ODE 独立推导。端点代数因子避免相近水头相减；80 位直接积分、独立 Gauss/ODE 与完整区间静态分支/角点/孔口界限维持原预算。独立最终数学检查 35 项、额外契约/精度检查 15 项通过。适用对象是声明的理想箱体/椭球、同密度、充分通气、点孔口、准静态浮态；不补入空气压缩、惯性晃荡或未声明压力物理。

## 修复与独立拒绝证明

新验证器先后暴露并修正：反向转移被误当成必须非负、缺失/非布尔求解状态、残差/液体有效性遗漏、错误网格求解 CB、可变绑定船体输入漏检、父进程未绑定原始请求/检查清单/源码摘要，以及未覆盖 spawn/结果读取/发布的期限。报告保护处理输出归属、错 schema、混合代次、并发与介质失败；未知锁保留供明确恢复。生产几何/浮态/舱液/进水算法及方法版本没有改变，系数、求解精度与数值容差没有调宽。

首轮真实全矩阵 37/38、exit 1 的有符号账本失败，及最终候选因运行中源码变更被拒绝的 29 通过/1 错误/8 未开始都保留。OpenCode 两次审查未通过后又遇配额限制，Codex 按已授权的接管约定完成实现。独立审查仍由三路代理执行：运行器 49 个正反探针、报告 13+8 组协议探针、上述数学审查。[设计裁决与失败记录](<C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/core-verification-next-round-2026-10-10/design-revisions-and-failures.md>)包含验收脚本自身的主机名/null-device误判，不把它们算作计算核缺陷。

## 最终回归与实际复制包

核心 pytest **1134 passed、594 subtests、2 skipped、1 warning，466.74s，exit 0**；2 项为 WinError1314 创建符号链接权限不足，既有 `testbed_weights` 返回 dict 触发警告。打包器 **18 passed、7 subtests、1 权限跳过，1.09s，exit 0**。真实 Windows junction 与其他路径/归属控制通过；未跳过的测试不能代替这三条特定符号链接分支。既有 convergence_study 最终重跑 **98/98**，其 13 个来源摘要与当前文件相符。

91 文件显式清单复制到中文/空格目录，从陌生 cwd 用 `-P -S -B` 实跑 help/readme/quick；复制源码与原包摘要相同。另一次父进程加 15 个工作进程的审计重放拒绝网络及包/标准库外的数据依赖，仅允许本机主机名读取、OS null discard 设备与隔离临时输出，16 个审计记录均无联网或越界数据访问。单独审计只包裹入口，直接 CLI 测试未修改。

普通发布器当前仅选择 git-tracked 文件，因此 5 个新验证模块仍待今后获授权的提交纳入；本地显式复制包验收通过不等于已发布。基线 346 文件中，允许变更之外的 343 个摘要保留，UI/字体/音效没有改写。报告发布不是三文件事务，非合作外进程在最后检查与 OS 替换之间的微小竞态没有被消除；同一次公共调用内恢复的瞬时输入改动也不属于净变化检测范围。

## 新鲜性能样本

每种负载三次串行新测量，执行于上述回归/全矩阵/复制计算结束后。CPython 3.12.14，Windows 11，AMD64 Family 25 Model 117 Stepping 2；具体解释器、CPU 描述、核心数、字面输入、原始状态和源码摘要在 [性能证据](<C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/core-verification-next-round-2026-10-10/final-performance/performance.json>)。

| 负载 | 中位数 wall 秒 | 最大 wall 秒 |
|---|---:|---:|
| quick-cli | 22.532 | 22.882 |
| flooding-single-sea-coupled-box-300s-dt0p125 | 28.175 | 28.301 |
| flooding-two-tank-asymmetric-free-float-300s-dt0p125 | 25.825 | 25.969 |

quick 包含子进程和报告发布；两个长负载只计公开 simulate_flooding 调用。它们是不同工作量，不能互比作速度评分；上限 300s、dt=0.125s 的实际停止时间/步数见上文与每份原始记录。

## 外部实测准备度

尚未取得或比对原始试验数据。候选为 [ITTC/TKK 1:10 驳船](https://ittc.info/media/3495/volume2_6stabilityinwave.pdf)、[FLARE 作者机构记录](https://repository.tudelft.nl/record/uuid:b12da2fb-48f6-406d-b6c1-f0aa50736dee)和 [NMRI KCS 目录](https://t2015.nmri.go.jp/kcs.html)；访问与输入可用性记录在快照。USBR 孔口手册是模型/系数适用参考，不能代替船体实验。下一步须取得精确 hull/loading/tank/orifice/Cd/vent、原始时间序列和不确定度，固定可比量和误差预算后再独立比对。解析一致、收敛与软件回归不证明全面超越 SPS，也不构成法定或船级认证。
