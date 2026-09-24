# 长任务：把剩余 SPS 页面做成「可输入表单」（一次性做完）

目标：让 Plimsoll 网页的 Guns / Weapons / Armour / Engines / Performance / Hull 各页像
SpringSharp 那样，有**可编辑的数据框**，而不是结构化 JSON 文本框。
已完成样板：**Freeboard 页**（`5699a58` 契约+投影 → `09c36d6` 接入 deck 阶段 → `3550b4f` 表单）。

状态基线：HEAD `3550b4f`，核心 **707 项全绿**、前端 **18 项全绿**、构建绿。

---

## 1. 统一三步样板（每页照抄）

| 步 | 做什么 | 落点 |
|---|---|---|
| **A 契约** | 给该页的输入加**声明字段**（fact 形状 `{value, source, estimate}`），并在校验器放行+校验 | `tools/plimsoll/project_extensions.py` |
| **B 投影** | 纯函数 `dict→dict`：按声明聚合、给覆盖度/未知清单/诊断；**不从别处反推** | `tools/plimsoll/page_rows.py` |
| **C 表单** | 工作台该章 JSON 框 → 表单（数字/文本/三态估算），聚合值取自运行结果 | `web/frontend/src/components/*Editor.tsx` + `Workbench.tsx` 分派 |

### 每页必守的纪律（缺一不可）
1. **未知 ≠ 零**：`null`/缺失显示「未知」，`placeholder="未知"`，清空不得写 0。
2. **不在 TS 里复算**：加权平均、覆盖度等聚合值一律取自运行结果（`stages.*.data.*`），前端只展示。
3. **先声明后投影**：契约没有的字段，UI 不画框、投影不猜值。
4. **诊断而非静默**：缺输入 → `page_rows.*` 诊断（非阻塞），列出未知项。
5. **口径可分**：「声明输入」与「实测/当前浮态」字段必须不同名。

---

## 2. 为什么串行（并发规则）

共享文件：`page_rows.py`（投影）、`project_extensions.py`（校验）、`Workbench.tsx`（UI 分派）。
**同一时刻只允许一个工作包改这些文件** → 页面按序推进；只有「前端新组件文件」这类独占新文件可并行。

顺序（按数据就绪度，先易后难）：

```
W1 Guns → W2 Weapons → W3 Armour → W4 Engines → W5 Performance → W6 Hull
```

---

## 3. 各工作包（每个包四步：侦察 → A → B → C，各自提交）

### W1 · Guns
- 现状：`systems.weapons.main/secondary` 已有 `installed_guns` / `broadside_guns` / `rounds_per_gun`；核心已能按「有来源的单发弹丸质量 × 单舷炮数」算齐射弹重，并与全舰携带量分开。
- 做：确认单发弹丸质量的声明位置 → 如缺则加 fact → 投影出「齐射弹重 / 每门携带 / 全舰弹药」→ 表单（门数/单舷门数/每门弹数/单发弹丸质量 + 来源 + 估算）+ 展示炮座旋转装甲拆分。
- 验收：清空不写 0；齐射弹重来自后端；QM 无来源处显示未知。

### W2 · Weapons
- 现状：鱼雷/水雷/深弹支持重复类型化声明；无账本绑定质量为 `null`；**五个杂项位置分区仍缺可靠质量分配**。
- 做：杂项五分区的声明字段（若契约无则加）+ 投影（各分区质量与覆盖）+ 表单（鱼雷管数/携带/雷径/布置；水雷/深弹计数；五分区质量）。
- 红线：QM 五个分区**没有数据就保持未知**，不得按排水量倒填。

### W3 · Armour
- 现状：装甲行已按非重叠账本条目分组求小计，含已声明厚度/跨度/类型；另有 `deck_coverage`、`minimum_main_belt`、`rotating_armour_component` 三个可选研究。
- 做：表单编辑每行的厚度/跨度/类型 + 上述三个研究的输入，展示分组小计与三个研究结论（含 `unavailable` 原因）。
- 红线：`minimum_main_belt` 明确不是 SPS 原公式；缺完整范围返回 `unavailable`。

### W4 · Engines
- 现状：锅炉事实、所选机械质量、煤/油绑定、显式指定的燃料/水/其他可变载荷分组；动力构型有能源与传动类型事实。
- 做：表单编辑这些事实与分组绑定；展示燃料/续航相关结果（来自运行，不前端复算）。
- 红线：可变载荷不是第二份排水量。

### W5 · Performance
- 现状：`Normal/Deep` 工况有；**Standard/Light 仍缺显式定义**；横摇周期只在 GM、型宽、有源回转半径系数齐备时计算。
- 做：先为 **Standard/Light 定义扣除规则**（七页清单要求"必须显式定义，不可猜测扣除载荷"），再给表单与结果展示。
- 红线：不实现 SPS 专有的 Stability/Seakeeping 评分与 Damage sustainability 等级；不实现 Cost & Strength。

### W6 · Hull
- 现状：主尺度 6 个字段已可编辑（LOA/水线长/型宽/吃水/方形系数/水线面系数）。
- 做：侦察 SPS Hull 页还有哪些输入在契约里缺失 → 补声明 + 表单（不要把主尺度的 6 个框拆掉）。
- 红线：`hull.derived.natural_speed` 保持未实现（SPS「自然速度」无公认定义，是七页清单剩余 2 条之一）。

---

## 4. 明确不做（写进文档，不要偷偷做）

- SPS 专有评分：Stability / Seakeeping / Damage sustainability 等级
- Cost & Strength（历史造价、结构强度）—— 规格排除项
- `hull.derived.natural_speed` —— 无公认定义
- `guns.battery_selection.editor_fields_unknown` —— 电池编辑器字段未被观测（七页清单剩余 2 条之一）
- 公网部署、真实邮件、并发/多机负载证据（属另一条线）

---

## 5. 每个包的完成判据（统一）

1. 侦察报告：该页在 `evidence/seven-page-binding-proposal.json` 里有哪些条目、当前是 `implemented*`/`input_conditional`/未声明。
2. 核心：新投影有单元测试（合成输入 + QM 集成）；**全量回归 `run=<707+N> fail=0`**。
3. 前端：表单组件 + `Workbench.tsx` 分派；新测试（输入写入 / 清空不写 0 / 无运行记录显示提示）；**`vitest run` 与 `npm run build` 全绿，既有 18 项仍通过**。
4. 提交（不 amend、不推送），消息格式 `feat(...): ...`，回报哈希 + 字段对应表 + 测试数字。

## 6. 风险与停手条件

- 若某页的 SPS 输入**没有可靠来源且 QM 无数据** → 保持未知并写进文档，**不要倒填**。
- 若改动会破坏既有契约（校验器或阶段 `data` 键集合有严格断言）→ **停下报告冲突点**，不要强行放宽。
- 若前端需要 `npm ci` → 先报告，不要自行联网安装或改 lockfile。
