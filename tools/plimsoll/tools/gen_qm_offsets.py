# -*- coding: utf-8 -*-
"""物化 Queen Mary 型值表 → cases/queen_mary_1913_offsets.json。

**通用性改造（2026-09-22）**：此前 cli.py 会在运行时扫描仓库路径、甚至解析
queen_mary_v4.py 脚本取内建表 —— 项目专属逻辑混进了通用 CLI。改造后：

  - CLI 只认「案例声明的 offsets_path 或 --offsets 参数」；
  - 本船的型线一次性物化为本案例自带的 JSON（schema plimsoll-offsets-1），
    Queen Mary 从此和其他任何船一样，只是一个普通案例。

跑法：python tools/plimsoll/tools/gen_qm_offsets.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))
sys.path.insert(0, PKG)

import offsets as OF  # noqa: E402

# 生成脚本 DECK_Z（主甲板高，模型坐标水线 z=0）—— 生成器是 QM 的数据适配器，
# 允许知道这艘船的具体数值；核心 offsets 模块已不再提供该默认值。
DECK_Z = 5.10

OUT = os.path.join(PKG, "cases", "queen_mary_1913_offsets.json")


def main():
    script = os.path.join(REPO, "queen_mary_v4", "queen_mary_v4.py")
    table = OF.parse_offsets_from_python(script)
    payload = {
        "schema": "plimsoll-offsets-1",
        "ship": "HMS Queen Mary (1913)",
        "deck_z_m": DECK_Z,
        "source": ("queen_mary_v4.py 内建 OFFSETS（生成脚本自述形状为 estimate，"
                   "非史实型线）；拿到型线图后直接替换本文件的 stations 即可"),
        "coordinates": "x 沿船长(+艏) / y 右舷 / z 上；水线 z=0；每站 (y, deck_hb, wl_hb, keel_z, flat_hb)",
        "stations": [list(r) for r in table],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("written:", OUT, "(%d stations)" % len(table))


if __name__ == "__main__":
    main()
