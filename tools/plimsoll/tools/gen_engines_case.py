# -*- coding: utf-8 -*-
"""生成 Engines 页案例（plimsoll-engines-1）—— Queen Mary 1913。

来源（Navypedia / 维基，逐项带出处）：
  轴数 4（Navypedia "No of shafts 4"）
  主机 4 × Parsons 蒸汽轮机（直驱）；锅炉 42 × Yarrow（燃煤、喷油助燃）
  功率 设计 75,000 shp（两源一致）；试航 83,000 shp → 28.1 kn（Navypedia）
  航速 最大 27.5 kn（Navypedia）；巡航速度**无来源** → 置空
  燃料 煤 3,600 t + 油 1,170 t（最大装载；维基）
  续航 5,610 nm @ 10 kn（Navypedia / 维基）

**未采集**：Engine weight（主机重量）、Displacement factor。
**明确不做**：Friction/Wave resistance（需 Holtrop-Mennen / Taylor，PLAN 7.3 独立项）。

跑法：python tools/plimsoll/tools/gen_engines_case.py > tools/plimsoll/cases/queen_mary_1913_engines.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)


def main():
    case = {
        "schema": "plimsoll-engines-1",
        "ship": "HMS Queen Mary (1913)",
        "displacement_normal_t": 26770,
        "lwl_m": 212.8,
        "_note": ("Engines 页 v0（只做有源部分）：主机/锅炉/燃料/续航为文献值；"
                  "巡航速度、Engine weight、Displacement factor 无来源 → 置空。"
                  "Friction/Wave resistance 需要 Holtrop-Mennen / Taylor 阻力模型，"
                  "属 PLAN 7.3 独立项，本页不估算。"),
        "shafts": 4,
        "shafts_source": "Navypedia: No of shafts 4",
        "engine_type": "4 × Parsons 直驱蒸汽轮机",
        "engine_type_source": "Navypedia: 4 Parsons steam turbines；维基同",
        "boilers": {"type": "Yarrow 燃煤（喷油助燃）", "count": 42},
        "boilers_source": "Navypedia: 42 Yarrow boilers；维基 42 台锅炉",
        "power_design_shp": 75000,
        "power_design_source": "Navypedia 75,000 hp；维基 75,000 shp（两源一致）",
        "power_trial_shp": 83000,
        "power_trial_source": "Navypedia: on trials made 28.1 kts with 83,000 shp",
        "max_speed_kn": 27.5,
        "max_speed_source": "Navypedia: Max speed 27.5 kts（试航 28.1 kn @ 83,000 shp；设计 28 kn）",
        "coal_t": 3600.0,
        "oil_t": 1170.0,
        "fuel_source": "维基: 最大装载 3,600 t 煤 + 1,170 t 油",
        "range_nm": 5610.0,
        "range_at_speed_kn": 10.0,
        "range_source": "Navypedia: Endurance 5,610 nm (10 kts)；维基同",
    }
    json.dump(case, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
