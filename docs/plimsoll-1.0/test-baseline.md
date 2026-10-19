# 测试基线与运行方式 · 2026-10-19

在此之前，每轮验收只跑「相关簇」（12 文件 199 用例），跨模块的过期断言因此漏过一次：`native-design-projection` 在**全量 73 文件**里是红的，而簇里看不见。自此把**全量**定为基线。

## 命令

前端（在 `web/frontend`）：

```text
npx vitest run          # 等同 npm test
```

后端（在仓库根目录）：

```text
web/backend/.venv/Scripts/python.exe -B -m pytest web/backend/tests -q
```

**不需要手设 PYTHONPATH**：`web/backend/pyproject.toml` 的 `[tool.pytest.ini_options]` 已声明
`pythonpath = [".", "../../tools"]`（前者是本包，后者是计算核心；两者是兄弟目录）。

核心套件（本轮未纳入基线，仅记录历史值）：

```text
web/backend/.venv/Scripts/python.exe -B -m pytest tools/plimsoll/tests -q
```

## 当前基线（2026-10-19 实测）

| 套件 | 结果 | 耗时 |
|---|---|---|
| 前端全量 | **1,454 用例全部通过**（73 文件 / 346 套件） | ~55 s |
| 后端 | **187 通过 / 2 跳过** | ~125 s |
| 核心（历史） | 2026-10-10 记录为 1,134 passed / 594 subtests | ~467 s |

**任一红灯不得进入发布。** 相关簇仍可用于快速迭代，但发布前的最后一道必须是全量。

全量套件本身也要能稳定复跑：`leave-guard.test.tsx` 的装配用例等懒加载的工作台章节导航只用了 `findByRole` 的 1 秒默认等待，机器一忙就会红。已改为 5 秒并连跑三次确认稳定——基线不稳定的等于没有基线。

## 本轮修掉的那条红灯

`native-design-projection` 原本断言「原生结果旁边仍显示旧 balance 区块」，而上一轮已把该区块改为
`{balance && !native}`——权威平衡改由受管重量读数（`data-weight-balance-row`）承载。产品行为正确，是断言过期。

改为两条针对性用例：

1. **台账可读**：四项权威值出现在 `[data-weight-balance-row]`，且不再有 `.ship-design-balance` 重复块；
2. **台账缺失**：读数 `data-state="unavailable"`，且	extbf{不引用任何 balance 数字}（原始审计区仍可照录载荷原文）。

第二条把上一轮「没有台账就不许漏出余额」的意图第一次钉进了测试。
