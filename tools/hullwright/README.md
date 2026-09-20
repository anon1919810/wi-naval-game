# hullwright

自研舰船设计与静水力计算核心。规格见 [`docs/sps-replacement/SPEC.md`](../../docs/sps-replacement/SPEC.md)。
与 SpringSharp **无代码关系**；其界面仅作需求覆盖度检查表（参考图在 `docs/sps-reference/`）。

## 当前进度：L0（参数化静水力）

```bash
PY="C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe"

# 算一艘船
"$PY" tools/hullwright/cli.py tools/hullwright/cases/queen_mary_1913.json \
        -o tools/hullwright/cases/queen_mary_1913.result.json

# 核心自检
"$PY" tools/hullwright/cli.py --selftest

# 单元测试（28 项）
"$PY" tools/hullwright/tests/test_hydrostatics.py
```

输出：排水量、水线面面积、每厘米吃水吨数、KB、BM_T、KM、GM、横摇周期、
BM_L、每厘米纵倾力矩，外加 **KG 敏感性表**与 **逐项 trace（formula + source + estimate）**。

## 船体形状模型（L0 的关键设计）

没有型线图时，唯一诚实的做法是**声明形状假设**而不是塞经验魔数。本核心用一参数模型：

```
半宽分布  f(x) = (1 − (2x/L)²)^p ,  x ∈ [−L/2, L/2]
```

只有一个参数 `p`，各阶矩可解析求出（Γ 函数），给定 `Cwp` 反解 `p` 后其余量**唯一确定**，
不存在"再挑几个系数"的自由度。`p = 0` 退化为方箱，此时

```
Cwp = 1,  C_I = 1,  I_T = L·B³/12,  I_L = B·L³/12,  KB = T/2,  BM_T = B²/(12T)
```

单元测试正是断言这组解析值——**模型自洽性由闭式解保证，不靠调参**。

## 按纪律写死的几条

- 核心**纯函数**：`dict → dict`，不 import GUI / Unity / 网络库。
- 核心**不做四舍五入**：全精度 float，取整只发生在 CLI 显示层。
- 每个输出项都有 `formula` / `source` / `estimate`；测试断言 trace 覆盖全部值且都有来源。
- `estimate` 成分在输出里带 `*` 标记，并在 warnings 里点名。

## 已知未决（诚实清单）

| 项 | 状态 |
|---|---|
| `waterplane_coeff = 0.80` | **estimate**，无来源。待 L1 几何法从真实船体算出后替换 |
| `kg_m = 8.6` | **estimate**，KG 属 L2 重量分组。GM 与之强耦合，故输出附 KG 敏感性表 |
| 水线长口径 | 205.7 m（675 ft，疑似两柱间长）vs 契约 213.4 m（700 ft）待考证 |
| 吨位单位 | 史料常混用长吨/公吨，本核心内部按公吨 |

## 与项目现有资产的关系

游戏侧 `ShipFloatPrototype.cs` 用的是 `waterplaneAreaM2 = 4610.4`，**无来源**。
反推其隐含 `Cwp = 4610.4 / (205.7 × 27.1) = 0.827`。本核心在 `Cwp = 0.80` 下算出
**4459.6 m²**，与之相差 3.3%——说明那个常数不算离谱，但它现在是**可复算、可溯源**的了。
`TestCrossChecksAgainstProjectAsset` 把这条对照关系固化成了测试。
