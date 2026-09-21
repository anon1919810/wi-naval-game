# Plimsoll 破损计算、警告传递与数据口径修正

日期：2026-09-22。基于本地 `master` 的 `e1596ea` 工作树。
本次范围为 Plimsoll 求解器、案例生成器、回归与文档；没有更改 Unity 工程或舰船网格。

## 1. 破损计算

矩形舱从底部均匀进水，水深为 `f × H`，水体重心应为 `z0 + f × H / 2`。
旧实现使用 `z0 + f × H`，实际取到了液面，导致合成 KG 偏高、GM 偏低。
`permeability` 仍表示均匀可进水体积比例，不再额外缩放水深或重心。
这是明确的矩形代理假设，不能代表舱内非均匀机器、管道和分隔造成的真实液体分布。

无水、零渗透率或关闭自由液面的舱不再产生 FSC；`flood_tanks_to_fs_tanks()` 的 GZ 旁路也遵守相同规则。
FSC 分母仍为进水后的排水量，已计入 KG 的 FSC 不再在 GZ 中重复添加。

已重新生成三个确定性案例。它们是合成参考船体的测试工况，保留原始基线用于比较，不能当作 Queen Mary 史实破损稳性：

| 案例 | KG_eff 旧 → 新，m | 破损 GM 旧 → 新，m |
|---|---:|---:|
| single_boiler | 8.821939 → 8.789583 | 4.232193 → 4.264549 |
| double_boiler | 9.030866 → 8.940412 | 3.912007 → 4.002461 |
| engine_room | 9.084965 → 8.917389 | 3.821949 → 3.989525 |

三例原有增重和解算目标未变；原有 `stable` 布尔值仍为 True。这个布尔值只是当前简化判据，不是损管安全认证。

## 2. 警告随结果传递

- `speed_power_curve()` 保留 Schoenherr 越界、图谱轴截断、缺格插值警告；每点带 `warnings`、`trace`，汇总警告附航速。
- 缺表或所需角点全缺失时，`Cr / Rr / Rt / EHP / SHP` 保持 `None`，`complete=False`。摩擦阻力仍可查看，不能冒充总阻力。
- 汇总最大值仅取有效点，全无有效点时为 `None`，并提供 `complete_points`。
- 图谱恰在端点不再误报越界；零权重角点不再制造缺格警告。缺格按原插值权重归一化，不是等权平均；截断误差方向未知。
- Engines 页快照合并计算与阻力警告，缺剩余阻力时仍列为缺项，`displacement_factor` 始终保留未实现状态。
- HTML 缺值显示破折号，曲线在缺值处断开，列出实际 Fr 和逐点诊断；试航比较使用同一个 28.1 kn 点。
- CLI 的 GZ 输出保存载荷、体积、水线基准、估算标记及甲板浸没警告，并把这些警告并入 JSON 顶层。

`complete=True` 仅代表计算链有值，不代表在所有适用范围内，更不代表史实验证通过。

## 3. 统一正常载荷估算口径

正常载荷基准由 `cases/queen_mary_1913.json` 与共享适配器 `tools/qm_resistance_inputs.py` 生成。
单点阻力与速度曲线使用完全相同的参数对象，不再各自复制常数。

| 参数 | 当前值与依据 |
|---|---|
| Lwl / B / T | 212.8 / 27.1 / 8.5 m，正常载荷 |
| 排水量 / 密度 | 26770 公吨 / 1.025 t/m³；原史料吨位单位仍未确认 |
| Cb | 0.5328005513580124，由同载荷排水量和尺度反推，保留精度 |
| Cm | 0.94，假设，不是 Queen Mary 的实测最大横剖面系数 |
| Cp | 0.5668090971893749，由 Cb/Cm 推得，继承估算 |
| 湿表面积 S | 6147.556844 m²，同载荷 Mumford 经验式估算 |
| QPC | 中值 0.55，敏感性带 0.50 / 0.55 / 0.60，均为假设 |

模型 `z=0` 对应吃水 9.9 m，几何积分湿面积约 6407.873 m²。它与正常载荷 8.5 m 的经验式值不能作为“同一载荷下两法互证”。
满载模型的 L、S、Cp、B/T、体积全部单列用于对照，禁止挪用其中 S 到正常载荷曲线。

28.1 kn、QPC=0.55 的当前正常载荷估算：

- 摩擦阻力 1159.817 kN，表插值 Cr=0.0013958723。
- 预测轴功率 73272.446 shp；相对 83000 shp 试航参考为 **−11.7199%**。
- 试航功率反解 Cr=0.0018150526；表预测功率反解 QPC=0.4855403。
- 满载模型对照反解 QPC=1.0543390；旧文档的“0.28”错误，作废。

试航实际载荷未确认，史料吨位单位未确认，Cm、S、QPC 含假设，且试航速度的 Rn 超出当前 Schoenherr 函数声明区间。这些数值只供诊断。
撤销“两个独立来源互证”和“偏差接近 5–10% 所以通过验收”的旧结论，不按试航点反调参数。

## 4. 估算标记与迁移

输入增加 `waterplane_coeff_is_estimate`、`block_coeff_is_estimate`、`displacement_unit_is_estimate`。
未声明的 Cwp/Cb 来源默认按估算处理。Cwp 估算传播到水线面、BM、MCT；KB 的 Morrish 近似使 KM、GM 继续标估算，即使 KG 本身有实测来源。
模型型线的积分结果与全部 trace 继承 `estimate=True`，并补上湿面积 trace。

L0 正常载荷与 CLI 型线 GZ 设计水线仍是两种独立工况，输出已显式区分；本次没有把后者改为正常载荷求解。

生成阻力/曲线案例 schema 升为 `plimsoll-resistance-2` / `plimsoll-speed-power-2`：

- `hull_params_historical` → `hull_params_normal_estimate`。
- 单点参数改为 `inputs.normal_estimate` 与 `inputs.model_full_load`。
- `cr_table_historical` → `cr_table_normal_estimate`。
- `qpc_implied_by_table_historical` → `qpc_implied_by_table_normal_estimate`。
- 预测总量见 `normal_prediction`，满载对照见 `model_full_load_prediction`；原 `values.r_total_kN/rr_kN` 明确为试航功率在假定 QPC 下的反解。

本地已检查到的生成器与测试已迁移；外部读取脚本如依赖 v1 字段须按上述映射调整。数值为空时不能转换为 0。

## 5. 验证与复现

新增回归先对旧实现运行并复现失败，再修正实现。物理重心使用独立手算水体中点；旧测试中镜像了错误公式的期望已修正。
移除把假定参数贴近试航结果视为“历史认证”的测试，保留公式、插值、边界与生成案例一致性验证。

六项临时变异均被针对性测试捕获，随后逐字节恢复源码：旧进水重心、无水 FSC、丢弃聚合警告、摩擦冒充总阻力、丢失 Cwp 估算、重新混入满载湿面积。

全量回归结果：`Ran 325 tests in 118.666s / OK`，`PLIMSOLL_REGRESSION run=325 fail=0`。

复现顺序：主案例 → `tools/gen_engines_case.py`（stdout 保存为 Engines JSON）→ `tools/gen_formcoeff_case.py` → `tools/gen_resistance_case.py` → `tools/gen_speed_power_case.py`。
破损案例运行 `run_damage_scenarios.py`，L0/GZ 运行 `cli.py cases/queen_mary_1913.json --gz -o cases/queen_mary_1913.result.json`，全量回归运行 `run_all_tests.py`（以上命令相对 `tools/plimsoll`）。

## 6. 后续边界

下一轮优先补输入来源：吨位单位、试航载荷、Lpp 与图谱长度定义、真实 Cm/型线，以及适用范围校核。
破损求解仍为增重法、矩形舱、直立水线近似 KM 与小角度横倾；尚未实现连通进水、随倾角变化的液体几何和完整失稳判据。不要据当前测试全绿宣称真实舰船损伤预测已完成。
