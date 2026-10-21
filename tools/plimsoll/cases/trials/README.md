# 试航数据集（plimsoll 一等资产）

实测的军舰试航功率与航速，逐条带出处。**这是资产，不是拟合集** —— 它可以被引用、被核对、被用来给模型打分，
但不能在上面调参数（数据集的输出段只有 5 条时会警告：n<8 不许拟合）。

## 目录

| 文件 | 作用 |
|---|---|
| `dataset.json` | 数据本体（schema `plimsoll-trial-dataset-1`，SI 单位） |
| `../../trial_dataset.py` | 读取 / 校验 / 统计模块 |
| `../../tests/test_trial_dataset.py` | 完整性、闸门、统计口径与固定值测试 |

## 一条记录长什么样

```json
{
  "id": "hms-hood-1920",
  "name": "HMS Hood", "navy": "Royal Navy", "ship_type": "battlecruiser", "year": 1920,
  "hull":  { "length_m": 257.1, "length_basis": "lbp", "beam_m": 31.75, "draught_m": 9.75,
             "displacement_t": 42200, "block_coeff": 0.517, "block_coeff_basis": "..." },
  "trial": { "shp": 151280, "speed_kt": 32.07, "kind": "full_power", "date": "1920",
             "load_note": "trial at 42,200 t on the Arran mile; draught is the deep-load figure" },
  "source":       { "url": "https://...", "retrieved": "2026-10-21", "quote": "…the sentence…" },
  "verification": { "status": "hand_checked", "notes": "…" },
  "model":        { "predicted_hp": 185244, "error_pct": 22.45, "commit": "409be70" },
  "sensitivity_pct": { "deep displacement 47,429 t + deep draught": 35.27 }
}
```

## 五条硬规矩（校验器强制）

1. **必须带原文引文**（`source.quote`）：只写 "维基百科" 不算出处，要能摘出那一句。
2. **必须标试航类型**（`trial.kind`）：full_power / measured_mile / three_hour / acceptance。
   同一条船不同试航给出不同的数（Hood：151,280 shp 全功率 vs 150,473 shp 三小时），混用没有意义。
3. **必须写载况**（`trial.load_note` + 排水与吃水）：载况混用让 Hood 的误差移动了 **13 个百分点**。
4. **必须写长度基准**（`hull.length_basis` = lbp/loa）：LOA 换 LBP 让 Hood 的误差移动了 **10 个百分点**。
5. **合理性闸门**：航速 15–40 kn、shp/排水量 0.5–40；越界一律拒绝（曾抽到 "41,000 shp @ 10 kn" 这样的垃圾）。

## 当前规模与统计（n=12）

| 口径 | MAPE | 中位 | 区间 |
|---|---|---|---|
| 全部（12） | 9.88 % | 7.37 % | -13.17 % … +25.92 % |
| 战列巡洋舰（3） | 22.81 % | 22.45 % | +20.06 % … +25.92 % |
| 战列舰（9） | 5.57 % | 5.40 % | -13.17 % … +9.27 % |
| 航速 24-30 kn（1） | 13.17 % | 13.17 % | -13.17 % … -13.17 % |
| 航速 30+ kn（4） | 17.21 % | 21.25 % | -0.43 % … +25.92 % |
| 航速 under 24 kn（7） | 5.22 % | 5.40 % | -10.94 % … +9.27 % |
| Fr 0.24<=Fr<0.28（7） | 5.78 % | 5.40 % | -13.17 % … +5.40 % |
| Fr Fr>=0.28（5） | 15.63 % | 20.06 % | -0.43 % … +25.92 % |
| 0.50<=Cb<0.55（6） | 14.84 % | 15.50 % | -10.94 % … +25.92 % |
| Cb<0.50（3） | 2.75 % | 2.04 % | -5.46 % … +2.04 % |
| Cb>=0.55（3） | 7.09 % | 5.40 % | -13.17 % … +5.40 % |
| 长度基准 lbp（6） | 13.47 % | 14.66 % | -0.43 % … +25.92 % |
| 长度基准 loa（6） | 6.29 % | 5.43 % | -13.17 % … +5.40 % |


## 已经看出来的结构

- **误差在 31 kn 附近翻向**：Bismarck 30.1 kn 是 −0.43 %，而 31.7 kn 以上的四艘全部高估 20–26 %。
  所以"30 kn 以上都高估"是错的 —— 测试里明确写的是 31 kn 这条线。
- **误差不是均匀散布，是跟船型走**：这正是分段混合而不是全局因子的理由。

## 怎么加一条

1. 找到一条**自称试航**的原始句子（"during trials … provided X shp … reached Y knots"）；设计额定值一律不收。
2. 补齐 LBP、B、吃水、载况排水；Cb 用 排水/(LBP·B·吃水)/1.025 反算并在 `block_coeff_basis` 写明。
3. 跑一遍模型，记录 `predicted_hp` 与 `error_pct`（附 commit）。
4. 写进 `dataset.json`，跑校验：

       PYTHONPATH=tools python -m pytest tools/plimsoll/tests/test_trial_dataset.py -q

5. 若新数据推翻了既有结论（例如 31 kn 边界移动），**同时改测试**并在提交信息里说明原因。

## 与主报告的关系

公式与全部实测数据见 `docs/plimsoll-1.0/resistance-methods-and-data-2026-10-21.md`；
本数据集在那份报告里是 §7.3 的数据来源，也是"目标值必须先洗干净"这一结论的实证基础。
